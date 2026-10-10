"""Market Movement Predictor — walk-forward training and artifact serialisation.

This module is the OFFLINE training half of the ML pipeline.  It is never
imported by the API layer (market_ml.py) or any router.

Run from the backend directory:

    python -m app.services.market_ml_training
    python -m app.services.market_ml_training --symbol TCS.NS --horizon 1 3
    python -m app.services.market_ml_training --arch lr   # baseline only
    python -m app.services.market_ml_training --arch gbm  # GradientBoosting only

Design notes
------------
* scikit-learn is imported inside functions so that an ImportError at module
  load time cannot break the API server if the package were somehow absent.
* XGBoost is intentionally excluded per the specification constraint for this
  implementation pass.
* Two architectures are compared: LogisticRegression (baseline) and
  GradientBoostingClassifier (main candidate).  The best by average balanced
  accuracy across validation folds is saved.
* Walk-forward validation splits the timeline into at least 3 chronological
  folds.  A purge gap of `horizon` bars is inserted between each training fold
  end and the corresponding validation fold start to prevent label leakage from
  overlapping forward-return windows.
* StandardScaler is fit ONLY on training data; the fitted scaler is applied
  (not re-fit) to validation data.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FoldMetrics:
    fold: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    accuracy: float
    macro_f1: float
    balanced_accuracy: float
    brier_score: float
    confusion_matrix: list[list[int]]
    majority_class_baseline: float
    below_baseline: bool


@dataclass
class ModelArtifact:
    scope: str
    horizon: int
    arch: str
    training_date: str          # ISO 8601 UTC
    feature_names: list[str]
    return_threshold: float
    n_training_bars: int
    avg_accuracy: float
    avg_macro_f1: float
    avg_balanced_accuracy: float
    fold_metrics: list[FoldMetrics] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Walk-forward validator
# ---------------------------------------------------------------------------

class WalkForwardValidator:
    """Generate chronological (train_indices, val_indices) pairs.

    Split fractions
    ---------------
    * Initial training set  : first 60 % of bars
    * Purge gap             : `horizon` bars (excluded from both sets)
    * Validation window     : fixed slice of ~(20 / n_folds) % per fold
    * Final holdout         : last 20 % — never touched during cross-validation

    Folds expand forward (walk-forward): each subsequent fold adds the previous
    validation window to the training set.

    Parameters
    ----------
    n_bars:
        Total number of bars in the dataset.
    horizon:
        Forecast horizon in bars; also the purge-gap size.
    n_folds:
        Number of cross-validation folds (minimum 3).

    Raises
    ------
    ValueError
        When there are too few bars for the requested folds and purge gaps.
    """

    INITIAL_TRAIN_RATIO = 0.60
    HOLDOUT_RATIO       = 0.20

    def __init__(self, n_bars: int, horizon: int, n_folds: int = 3) -> None:
        if n_folds < 3:
            raise ValueError(f"n_folds must be >= 3 (got {n_folds})")

        self.n_bars  = n_bars
        self.horizon = horizon
        self.n_folds = n_folds

        holdout_bars    = max(1, int(n_bars * self.HOLDOUT_RATIO))
        holdout_start   = n_bars - holdout_bars      # first index of holdout
        available       = holdout_start              # bars available for CV

        # Initial training takes INITIAL_TRAIN_RATIO of the available (pre-holdout) bars.
        init_train  = max(1, int(available * self.INITIAL_TRAIN_RATIO))
        cv_bars     = available - init_train

        # Each fold needs a purge gap + a validation window.
        # Split remaining CV bars equally across folds.
        val_window  = max(1, (cv_bars - n_folds * horizon) // n_folds)

        # Sanity: we need at least one bar per validation window after the purge.
        min_required = init_train + n_folds * (horizon + val_window) + holdout_bars
        if n_bars < min_required or val_window < 1:
            raise ValueError(
                f"Not enough bars for {n_folds} folds with horizon={horizon}. "
                f"Need at least {min_required}, got {n_bars}. "
                "Reduce n_folds or collect more data."
            )

        self._init_train    = init_train
        self._val_window    = val_window
        self._holdout_start = holdout_start

    def splits(self) -> list[tuple[range, range]]:
        """Return list of (train_range, val_range) pairs in chronological order.

        The purge gap bars between each training end and the matching validation
        start are excluded from both ranges.
        """
        result: list[tuple[range, range]] = []
        train_end = self._init_train  # exclusive upper bound of training

        for _ in range(self.n_folds):
            val_start = train_end + self.horizon          # skip purge gap
            val_end   = val_start + self._val_window      # exclusive

            # Stop if validation window would bleed into the holdout.
            if val_end > self._holdout_start:
                break

            result.append((range(0, train_end), range(val_start, val_end)))
            train_end = val_end  # next fold's training set extends to here

        if len(result) < 3:
            raise ValueError(
                f"Only {len(result)} valid fold(s) could be constructed. "
                f"Need at least 3. Collect more data or reduce horizon."
            )

        return result


# ---------------------------------------------------------------------------
# Pipeline builders and evaluators
# ---------------------------------------------------------------------------

def _build_pipeline(arch: str):
    """Return a fresh sklearn Pipeline (scaler + classifier)."""
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if arch == "lr":
        from sklearn.linear_model import LogisticRegression
        clf = LogisticRegression(
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )
    elif arch == "gbm":
        from sklearn.ensemble import GradientBoostingClassifier
        clf = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
        )
    else:
        raise ValueError(f"Unknown arch {arch!r}; choose 'lr' or 'gbm'")

    return Pipeline([("scaler", StandardScaler()), ("clf", clf)])


def _evaluate_fold(
    pipeline,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    fold_idx: int,
    train_start_date: str,
    train_end_date: str,
    val_start_date: str,
    val_end_date: str,
) -> FoldMetrics:
    """Fit pipeline on training data only, evaluate on held-out validation fold."""
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
    )
    from sklearn.preprocessing import label_binarize

    # Fit: scaler is fit here on training data only.
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_val)
    proba  = pipeline.predict_proba(X_val)

    classes = list(pipeline.classes_)
    acc     = float(accuracy_score(y_val, y_pred))
    f1      = float(f1_score(y_val, y_pred, average="macro", zero_division=0))
    bal_acc = float(balanced_accuracy_score(y_val, y_pred))
    cm      = confusion_matrix(y_val, y_pred, labels=classes).tolist()

    # Brier score (mean over classes, one-vs-rest)
    y_bin = label_binarize(y_val, classes=classes)
    if y_bin.shape[1] == 1:
        y_bin = np.hstack([1 - y_bin, y_bin])
    brier = float(np.mean(np.sum((proba - y_bin) ** 2, axis=1)))

    # Majority-class baseline
    unique, counts = np.unique(y_train, return_counts=True)
    baseline = float(counts.max() / counts.sum())

    return FoldMetrics(
        fold=fold_idx,
        train_start=train_start_date,
        train_end=train_end_date,
        val_start=val_start_date,
        val_end=val_end_date,
        accuracy=acc,
        macro_f1=f1,
        balanced_accuracy=bal_acc,
        brier_score=brier,
        confusion_matrix=cm,
        majority_class_baseline=baseline,
        below_baseline=acc < baseline,
    )


# ---------------------------------------------------------------------------
# Public training entry point
# ---------------------------------------------------------------------------

def train_and_save(
    symbol: str = "NSE_ALL",
    horizons: list[int] | None = None,
    arch: str = "auto",
) -> dict[int, ModelArtifact]:
    """Fetch data, run walk-forward training, save model artifacts.

    Parameters
    ----------
    symbol:
        Ticker symbol to fetch data for, or the scope tag "NSE_ALL" which
        is treated as a single representative symbol (NIFTY ETF) for a
        general model.  Per-stock models can be trained by passing the
        symbol directly.
    horizons:
        List of forecast horizons to train.  Defaults to [1, 3, 5, 10].
    arch:
        'auto' trains both LR and GBM, keeps the winner.
        'lr'   trains the Logistic Regression baseline only.
        'gbm'  trains GradientBoostingClassifier only.

    Returns
    -------
    dict mapping horizon → ModelArtifact for each successfully trained model.
    """
    from app.services import market as market_service
    from app.services.market_ml import (
        FEATURE_COLUMNS,
        SYMBOL_SCOPE,
        engineer_features,
        generate_labels,
        _threshold_for_horizon,
        _model_dir,
    )
    import joblib

    if horizons is None:
        horizons = [1, 3, 5, 10]

    # Resolve the fetch symbol: "NSE_ALL" → use NIFTYEES.NS as proxy
    fetch_sym = symbol if symbol != "NSE_ALL" else "NIFTYBEES.NS"
    scope     = symbol  # scope tag used in artifact filenames

    log.info("Fetching 2y daily OHLCV for %s (scope=%s)…", fetch_sym, scope)
    df = market_service.get_history(fetch_sym, period="2y", interval="1d")

    if df is None or df.empty:
        log.warning("No history returned for %s; skipping training.", fetch_sym)
        return {}

    log.info("Fetched %d bars for %s.", len(df), fetch_sym)
    features = engineer_features(df)

    if features.empty:
        log.warning("Feature engineering produced no rows; skipping training.")
        return {}

    # Align df index with features (features may have dropped early NaN rows)
    df_aligned = df.loc[features.index]

    archs_to_try: list[str]
    if arch == "auto":
        archs_to_try = ["lr", "gbm"]
    elif arch in ("lr", "gbm"):
        archs_to_try = [arch]
    else:
        raise ValueError(f"arch must be 'auto', 'lr', or 'gbm'; got {arch!r}")

    results: dict[int, ModelArtifact] = {}
    model_dir = _model_dir()

    for h in horizons:
        threshold = _threshold_for_horizon(h)
        labels = generate_labels(df_aligned, h, threshold)

        # Align features and labels: drop rows where label is NaN.
        valid_mask = labels.notna()
        X_all = features[valid_mask][FEATURE_COLUMNS].values
        y_all = labels[valid_mask].values
        dates_all = features[valid_mask].index

        if len(X_all) < 60:
            log.warning("Horizon %dd: only %d labeled rows — skipping.", h, len(X_all))
            continue

        try:
            validator = WalkForwardValidator(len(X_all), horizon=h, n_folds=3)
            splits = validator.splits()
        except ValueError as exc:
            log.warning("Horizon %dd: walk-forward split failed — %s", h, exc)
            continue

        log.info("Horizon %dd: %d labeled bars, %d folds, threshold=%.3f",
                 h, len(X_all), len(splits), threshold)

        best_arch     = archs_to_try[0]
        best_bal_acc  = -1.0
        all_fold_metrics: dict[str, list[FoldMetrics]] = {a: [] for a in archs_to_try}

        for a in archs_to_try:
            for fold_i, (train_range, val_range) in enumerate(splits):
                X_tr = X_all[train_range]
                y_tr = y_all[train_range]
                X_vl = X_all[val_range]
                y_vl = y_all[val_range]

                # Skip degenerate folds where a class is missing in validation
                if len(np.unique(y_vl)) < 2:
                    log.debug("Horizon %dd fold %d arch %s: skipping (single class in val)", h, fold_i, a)
                    continue

                pipeline = _build_pipeline(a)
                fm = _evaluate_fold(
                    pipeline, X_tr, y_tr, X_vl, y_vl,
                    fold_idx=fold_i + 1,
                    train_start_date=str(dates_all[train_range.start].date()),
                    train_end_date=str(dates_all[train_range.stop - 1].date()),
                    val_start_date=str(dates_all[val_range.start].date()),
                    val_end_date=str(dates_all[val_range.stop - 1].date()),
                )
                all_fold_metrics[a].append(fm)
                log.info(
                    "  horizon=%dd arch=%s fold=%d acc=%.3f bal_acc=%.3f f1=%.3f baseline=%.3f%s",
                    h, a, fold_i + 1,
                    fm.accuracy, fm.balanced_accuracy, fm.macro_f1,
                    fm.majority_class_baseline,
                    " [BELOW BASELINE]" if fm.below_baseline else "",
                )

            fms = all_fold_metrics[a]
            if not fms:
                continue
            avg_bal = sum(f.balanced_accuracy for f in fms) / len(fms)
            if avg_bal > best_bal_acc:
                best_bal_acc = avg_bal
                best_arch    = a

        log.info("Horizon %dd: best arch=%s avg_bal_acc=%.3f", h, best_arch, best_bal_acc)

        # Train final model on all non-holdout data using the winning architecture.
        # Holdout = last 20 % of labeled rows (for evaluation transparency only).
        n_holdout  = max(1, int(len(X_all) * 0.20))
        n_train    = len(X_all) - n_holdout
        X_final    = X_all[:n_train]
        y_final    = y_all[:n_train]

        final_pipeline = _build_pipeline(best_arch)
        final_pipeline.fit(X_final, y_final)

        fms_best = all_fold_metrics[best_arch]
        avg_acc  = sum(f.accuracy for f in fms_best) / len(fms_best) if fms_best else 0.0
        avg_f1   = sum(f.macro_f1 for f in fms_best) / len(fms_best) if fms_best else 0.0
        avg_bal2 = sum(f.balanced_accuracy for f in fms_best) / len(fms_best) if fms_best else 0.0

        artifact = ModelArtifact(
            scope=scope,
            horizon=h,
            arch=best_arch,
            training_date=datetime.now(timezone.utc).isoformat(),
            feature_names=FEATURE_COLUMNS,
            return_threshold=threshold,
            n_training_bars=n_train,
            avg_accuracy=round(avg_acc, 4),
            avg_macro_f1=round(avg_f1, 4),
            avg_balanced_accuracy=round(avg_bal2, 4),
            fold_metrics=fms_best,
        )

        # Serialize
        joblib_path = model_dir / f"{scope}_{h}d_{best_arch}.joblib"
        json_path   = model_dir / f"{scope}_{h}d_{best_arch}.json"

        joblib.dump(final_pipeline, joblib_path, compress=3)

        meta_dict = asdict(artifact)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(meta_dict, fh, indent=2)

        log.info("Saved %s and %s", joblib_path.name, json_path.name)
        results[h] = artifact

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(
        description="Train DolFin market movement prediction models."
    )
    parser.add_argument(
        "--symbol",
        default="NSE_ALL",
        help=(
            "Ticker symbol to train on, or 'NSE_ALL' (default) to use NIFTYBEES.NS "
            "as a broad-market proxy.  Example: --symbol TCS.NS"
        ),
    )
    parser.add_argument(
        "--horizon",
        nargs="+",
        type=int,
        default=[1, 3, 5, 10],
        metavar="H",
        help="Forecast horizon(s) in trading days (e.g. --horizon 1 5).",
    )
    parser.add_argument(
        "--arch",
        choices=["auto", "lr", "gbm"],
        default="auto",
        help=(
            "Model architecture: 'auto' compares LR and GBM and keeps the winner, "
            "'lr' is Logistic Regression only, 'gbm' is GradientBoostingClassifier only."
        ),
    )
    args = parser.parse_args()

    results = train_and_save(
        symbol=args.symbol,
        horizons=args.horizon,
        arch=args.arch,
    )

    if not results:
        print("\nNo models were saved (see warnings above).")
        sys.exit(1)

    print(f"\n{'Horizon':>8}  {'Arch':>5}  {'Avg Acc':>8}  {'Avg F1':>8}  {'Avg BalAcc':>10}")
    print("-" * 48)
    for h, art in sorted(results.items()):
        print(
            f"{h:>7}d  {art.arch:>5}  "
            f"{art.avg_accuracy:>8.3f}  {art.avg_macro_f1:>8.3f}  "
            f"{art.avg_balanced_accuracy:>10.3f}"
        )
    print(f"\nArtifacts written to: {_model_dir_str()}")


def _model_dir_str() -> str:
    from app.services.market_ml import _model_dir
    return str(_model_dir())


if __name__ == "__main__":
    _main()
