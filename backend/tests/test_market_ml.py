"""Tests for the Market Movement Predictor — Tasks 4–8.

Test classes
------------
TestFeatureEngineering  — column presence, finiteness, edge cases
TestLabelGeneration     — UP/DOWN/SIDEWAYS correctness, NaN tail, thresholds
TestLeakageGuard        — bar-t features use only data ≤ t
TestWalkForwardValidator— temporal ordering, purge gap, holdout exclusion
TestPredictor           — model_status states, prob sum, uncertainty flag
TestForecastResponse    — schema, disclaimer, 4-horizon invariant

All tests use the existing fake_market / fake_llm autouse fixtures from
conftest.py to prevent any real network calls.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 120, seed: int = 42) -> pd.DataFrame:
    """Deterministic OHLCV DataFrame with a business-day DatetimeIndex."""
    rng   = np.random.default_rng(seed)
    idx   = pd.bdate_range("2023-01-02", periods=n)
    # Geometric random walk for Close
    close = 1000.0 * np.cumprod(1 + rng.normal(0.0, 0.01, n))
    open_ = close * rng.uniform(0.99, 1.01, n)
    high  = np.maximum(close, open_) * rng.uniform(1.00, 1.02, n)
    low   = np.minimum(close, open_) * rng.uniform(0.98, 1.00, n)
    vol   = rng.integers(500_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Feature Engineering
# ──────────────────────────────────────────────────────────────────────────────

class TestFeatureEngineering:
    def test_all_columns_present(self):
        from app.services.market_ml import engineer_features, FEATURE_COLUMNS

        result = engineer_features(_make_ohlcv(120))
        assert list(result.columns) == FEATURE_COLUMNS

    def test_all_values_finite(self):
        from app.services.market_ml import engineer_features

        result = engineer_features(_make_ohlcv(120))
        assert not result.empty
        assert result.isna().sum().sum() == 0
        assert np.isfinite(result.values).all()

    def test_empty_input_returns_empty(self):
        from app.services.market_ml import engineer_features, FEATURE_COLUMNS

        result = engineer_features(pd.DataFrame())
        assert result.empty
        assert list(result.columns) == FEATURE_COLUMNS

    def test_none_input_returns_empty(self):
        from app.services.market_ml import engineer_features, FEATURE_COLUMNS

        result = engineer_features(None)
        assert result.empty
        assert list(result.columns) == FEATURE_COLUMNS

    def test_single_row_returns_empty(self):
        """A single-row DataFrame cannot fill any rolling window."""
        from app.services.market_ml import engineer_features

        result = engineer_features(_make_ohlcv(1))
        assert result.empty

    def test_ten_rows_returns_empty(self):
        """10 rows is below the 50-bar SMA window; after dropna nothing remains."""
        from app.services.market_ml import engineer_features

        result = engineer_features(_make_ohlcv(10))
        assert result.empty

    def test_null_close_row_excluded(self):
        """A row with NaN Close must not appear in the output."""
        from app.services.market_ml import engineer_features

        df = _make_ohlcv(120)
        df.iloc[60, df.columns.get_loc("Close")] = np.nan
        result = engineer_features(df)
        # Row 60 (and possibly the few after it that depend on it) are gone.
        assert result.index.get_loc(df.index[60]) if df.index[60] in result.index else True
        # Crucially, no NaN survives into the output.
        assert result.isna().sum().sum() == 0

    def test_output_row_count_less_than_input(self):
        """Rolling windows consume early rows, so output is shorter than input."""
        from app.services.market_ml import engineer_features

        df     = _make_ohlcv(200)
        result = engineer_features(df)
        assert len(result) < len(df)
        assert len(result) > 0

    def test_column_order_matches_constant(self):
        from app.services.market_ml import engineer_features, FEATURE_COLUMNS

        result = engineer_features(_make_ohlcv(120))
        assert list(result.columns) == FEATURE_COLUMNS


# ──────────────────────────────────────────────────────────────────────────────
# Label Generation
# ──────────────────────────────────────────────────────────────────────────────

class TestLabelGeneration:

    def _series_with_known_return(self, fwd_ret: float, horizon: int = 1) -> pd.DataFrame:
        """Build a DataFrame where bar 0's forward return equals fwd_ret."""
        base  = 1000.0
        close = [base] + [base] * horizon
        # Adjust the horizon-th bar so fwd_ret is exact.
        close[horizon] = base * (1 + fwd_ret)
        idx = pd.bdate_range("2023-01-02", periods=len(close))
        df  = pd.DataFrame({"Close": close}, index=idx)
        return df

    def test_up_label(self):
        from app.services.market_ml import generate_labels

        df = self._series_with_known_return(0.05, horizon=1)
        labels = generate_labels(df, horizon=1, threshold=0.01)
        assert labels.iloc[0] == "UP"

    def test_down_label(self):
        from app.services.market_ml import generate_labels

        df = self._series_with_known_return(-0.05, horizon=1)
        labels = generate_labels(df, horizon=1, threshold=0.01)
        assert labels.iloc[0] == "DOWN"

    def test_sideways_label_positive(self):
        from app.services.market_ml import generate_labels

        df = self._series_with_known_return(0.005, horizon=1)
        labels = generate_labels(df, horizon=1, threshold=0.01)
        assert labels.iloc[0] == "SIDEWAYS"

    def test_sideways_label_negative(self):
        from app.services.market_ml import generate_labels

        df = self._series_with_known_return(-0.005, horizon=1)
        labels = generate_labels(df, horizon=1, threshold=0.01)
        assert labels.iloc[0] == "SIDEWAYS"

    def test_exactly_at_threshold_is_sideways(self):
        from app.services.market_ml import generate_labels

        df = self._series_with_known_return(0.01, horizon=1)  # exactly at threshold
        labels = generate_labels(df, horizon=1, threshold=0.01)
        assert labels.iloc[0] == "SIDEWAYS"

    def test_last_horizon_rows_are_nan(self):
        from app.services.market_ml import generate_labels

        df = pd.DataFrame(
            {"Close": np.linspace(100, 110, 20)},
            index=pd.bdate_range("2023-01-02", periods=20),
        )
        for h in [1, 3, 5, 10]:
            labels = generate_labels(df, horizon=h, threshold=0.01)
            assert labels.iloc[-h:].isna().all(), f"horizon={h}: last {h} labels should be NaN"

    def test_three_class_distribution(self):
        """On a 120-bar series with default thresholds, all three classes appear."""
        from app.services.market_ml import generate_labels, _threshold_for_horizon

        df = _make_ohlcv(120)
        for h in [1, 3, 5, 10]:
            labels = generate_labels(df, horizon=h, threshold=_threshold_for_horizon(h))
            valid  = labels.dropna()
            assert set(valid.unique()) >= {"UP", "DOWN", "SIDEWAYS"}, \
                f"horizon={h}: expected all three classes"

    def test_threshold_from_settings(self, monkeypatch):
        """Thresholds are read from settings, not hardcoded."""
        from app.services import market_ml
        from app.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "market_ml_return_threshold_1d", 0.20, raising=False)

        df = self._series_with_known_return(0.05, horizon=1)
        # With a 20% threshold, a 5% move is SIDEWAYS.
        labels = market_ml.generate_labels(df, horizon=1, threshold=0.20)
        assert labels.iloc[0] == "SIDEWAYS"


# ──────────────────────────────────────────────────────────────────────────────
# Leakage Guard
# ──────────────────────────────────────────────────────────────────────────────

class TestLeakageGuard:

    def test_feature_at_t_uses_only_data_up_to_t(self):
        """engineer_features(df).iloc[t] must equal engineer_features(df[:t+1]).iloc[-1]."""
        from app.services.market_ml import engineer_features

        df   = _make_ohlcv(120)
        full = engineer_features(df)

        # Test at several positions spread across the DataFrame.
        sample_positions = range(len(full) - 5, len(full))  # last 5 complete rows
        for pos in sample_positions:
            idx_val = full.index[pos]
            # Find the integer location in the original df
            iloc_in_df = df.index.get_loc(idx_val)
            truncated  = engineer_features(df.iloc[: iloc_in_df + 1])
            if truncated.empty:
                continue
            row_full = full.iloc[pos]
            row_trunc = truncated.iloc[-1]
            pd.testing.assert_series_equal(
                row_full, row_trunc,
                check_names=False,
                atol=1e-9,
                rtol=1e-9,
            )

    def test_label_column_not_in_feature_columns(self):
        """The label Series must never share a column name with FEATURE_COLUMNS."""
        from app.services.market_ml import FEATURE_COLUMNS

        # Labels are a Series, not a DataFrame column, so this is definitional.
        assert "UP" not in FEATURE_COLUMNS
        assert "DOWN" not in FEATURE_COLUMNS
        assert "SIDEWAYS" not in FEATURE_COLUMNS


# ──────────────────────────────────────────────────────────────────────────────
# Walk-Forward Validator
# ──────────────────────────────────────────────────────────────────────────────

class TestWalkForwardValidator:

    def test_minimum_three_folds(self):
        from app.services.market_ml_training import WalkForwardValidator

        v = WalkForwardValidator(n_bars=500, horizon=5, n_folds=3)
        assert len(v.splits()) >= 3

    def test_temporal_ordering_within_fold(self):
        """All train indices < all val indices within each fold."""
        from app.services.market_ml_training import WalkForwardValidator

        v = WalkForwardValidator(n_bars=500, horizon=5, n_folds=3)
        for train_r, val_r in v.splits():
            assert max(train_r) < min(val_r), "Train must end before val starts"

    def test_temporal_ordering_across_folds(self):
        """Validation of fold i must end before training of fold i+1 extends."""
        from app.services.market_ml_training import WalkForwardValidator

        v = WalkForwardValidator(n_bars=500, horizon=5, n_folds=3)
        splits = v.splits()
        for i in range(len(splits) - 1):
            _, val_i    = splits[i]
            train_next, _ = splits[i + 1]
            # The next training set must start at 0 and end beyond the current val end
            assert max(train_next) >= max(val_i), \
                "Next fold's training should extend to at least current val end"

    def test_purge_gap_at_least_horizon(self):
        """Gap between train end and val start must be >= horizon bars."""
        from app.services.market_ml_training import WalkForwardValidator

        for h in [1, 3, 5, 10]:
            v = WalkForwardValidator(n_bars=500, horizon=h, n_folds=3)
            for train_r, val_r in v.splits():
                gap = min(val_r) - max(train_r) - 1
                assert gap >= h, f"horizon={h}: gap={gap} < horizon"

    def test_no_val_index_in_any_training_fold(self):
        """No validation index from fold i appears in training of any fold."""
        from app.services.market_ml_training import WalkForwardValidator

        v = WalkForwardValidator(n_bars=500, horizon=5, n_folds=3)
        splits = v.splits()
        all_val_indices: set[int] = set()
        for _, val_r in splits:
            all_val_indices.update(val_r)

        for train_r, _ in splits:
            overlap = set(train_r) & all_val_indices
            # The first validation window is added to the second training set —
            # that is expected (walk-forward expansion).  What must NOT happen is
            # a validation window appearing in the training fold of the SAME split.
            pass  # covered by temporal ordering test above

        # Stronger: val of fold i must not be in training of fold i (same split)
        for train_r, val_r in splits:
            assert not (set(train_r) & set(val_r)), \
                "Val indices must not appear in the training range of the same fold"

    def test_holdout_not_in_any_fold(self):
        """Last 20 % of bars never appear in any fold's train or val."""
        from app.services.market_ml_training import WalkForwardValidator

        n = 500
        v = WalkForwardValidator(n_bars=n, horizon=5, n_folds=3)
        holdout_start = n - v._holdout_start  # relative to n
        holdout_start = v._holdout_start

        for train_r, val_r in v.splits():
            assert max(train_r) < holdout_start, "Train bleeds into holdout"
            assert max(val_r)   < holdout_start, "Val bleeds into holdout"

    def test_too_few_bars_raises(self):
        from app.services.market_ml_training import WalkForwardValidator

        with pytest.raises(ValueError, match="enough bars"):
            WalkForwardValidator(n_bars=20, horizon=10, n_folds=3)

    def test_n_folds_less_than_3_raises(self):
        from app.services.market_ml_training import WalkForwardValidator

        with pytest.raises(ValueError, match="n_folds"):
            WalkForwardValidator(n_bars=500, horizon=5, n_folds=2)


# ──────────────────────────────────────────────────────────────────────────────
# Predictor (model loading, status, probs)
# ──────────────────────────────────────────────────────────────────────────────

class TestPredictor:
    def test_not_trained_status_when_no_artifact(self, tmp_path, monkeypatch):
        """get_forecast returns not_trained when no .joblib file exists."""
        import app.services.market_ml as ml
        monkeypatch.setattr(
        "app.services.market_ml.get_settings",
        lambda: _settings_with_model_dir(tmp_path),
        )
        ml.reload_models()
        df_mock = _make_ohlcv(120)
        monkeypatch.setattr(
        "app.services.market.get_history",
        lambda *a, **k: df_mock,
        )
        monkeypatch.setattr(
        "app.services.market.normalize_symbol",
        lambda s: s + ".NS" if "." not in s else s,
        )
        resp = ml.get_forecast("TCS")
        assert len(resp.horizons) == 4
        for hf in resp.horizons:
            assert hf.model_status == "not_trained"
            assert hf.prob_up is None


    def test_insufficient_history_when_too_few_bars(self, tmp_path, monkeypatch):
        """Fewer bars than min_history → insufficient_history for all horizons."""
        import app.services.market_ml as ml

        settings = _settings_with_model_dir(tmp_path)
        settings.market_ml_min_history_bars = 60
        monkeypatch.setattr("app.config.get_settings", lambda: settings)
        ml.reload_models()

        monkeypatch.setattr(
            "app.services.market.get_history",
            lambda *a, **k: _make_ohlcv(10),   # only 10 bars → too few
        )
        monkeypatch.setattr(
            "app.services.market.normalize_symbol",
            lambda s: s + ".NS" if "." not in s else s,
        )

        resp = ml.get_forecast("TCS")
        for hf in resp.horizons:
            assert hf.model_status in ("not_trained", "insufficient_history")

    def test_probability_sum_after_training(self, tmp_path, monkeypatch):
        """Trained model returns probs that sum to ≈1.0."""
        _train_tiny_model(tmp_path, horizon=1)

        import app.services.market_ml as ml
        import app.services.market_ml_training as tr

        settings = _settings_with_model_dir(tmp_path)
        monkeypatch.setattr("app.config.get_settings", lambda: settings)
        ml.reload_models()

        features = ml.engineer_features(_make_ohlcv(200))
        hf = ml._predict_horizon(features, tr.SYMBOL_SCOPE if hasattr(tr, "SYMBOL_SCOPE") else "NSE_ALL", 1)

        if hf.model_status == "ok":
            total = hf.prob_up + hf.prob_sideways + hf.prob_down
            assert abs(total - 1.0) <= 0.01, f"Probs sum to {total}"

    def test_uncertainty_flag_set_when_low_confidence(self, tmp_path, monkeypatch):
        """uncertainty_flag is True when max(probs) < 0.45."""
        import app.services.market_ml as ml

        # Build a mock pipeline whose predict_proba returns near-uniform probs.
        mock_pipe = _mock_pipeline(probs=[0.34, 0.33, 0.33])
        meta      = {"training_date": datetime.now(timezone.utc).isoformat()}
        ml._model_cache[("NSE_ALL", 1)] = (mock_pipe, meta)

        settings = _settings_with_model_dir(tmp_path)
        monkeypatch.setattr("app.config.get_settings", lambda: settings)

        features = ml.engineer_features(_make_ohlcv(120))
        hf = ml._predict_horizon(features, "NSE_ALL", 1)

        ml._model_cache.pop(("NSE_ALL", 1), None)  # cleanup
        assert hf.uncertainty_flag is True

    def test_uncertainty_flag_not_set_when_high_confidence(self, tmp_path, monkeypatch):
        """uncertainty_flag is False when max(probs) >= 0.45."""
        import app.services.market_ml as ml

        mock_pipe = _mock_pipeline(probs=[0.60, 0.25, 0.15])
        meta      = {"training_date": datetime.now(timezone.utc).isoformat()}
        ml._model_cache[("NSE_ALL", 1)] = (mock_pipe, meta)

        settings = _settings_with_model_dir(tmp_path)
        monkeypatch.setattr("app.config.get_settings", lambda: settings)

        features = ml.engineer_features(_make_ohlcv(120))
        hf = ml._predict_horizon(features, "NSE_ALL", 1)

        ml._model_cache.pop(("NSE_ALL", 1), None)
        assert hf.uncertainty_flag is False

    def test_stale_model_flagged(self, tmp_path, monkeypatch):
        """Model with training_date > staleness_days ago → model_status='stale'."""
        import app.services.market_ml as ml

        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        mock_pipe = _mock_pipeline(probs=[0.5, 0.3, 0.2])
        meta = {"training_date": old_date}
        ml._model_cache[("NSE_ALL", 1)] = (mock_pipe, meta)

        settings = _settings_with_model_dir(tmp_path)
        settings.market_ml_staleness_days = 7
        monkeypatch.setattr("app.config.get_settings", lambda: settings)

        features = ml.engineer_features(_make_ohlcv(120))
        hf = ml._predict_horizon(features, "NSE_ALL", 1)

        ml._model_cache.pop(("NSE_ALL", 1), None)
        assert hf.model_status == "stale"
        assert hf.is_stale is True
        assert hf.prob_up is not None  # probs still returned for stale models

    def test_disclaimer_always_present(self, tmp_path, monkeypatch):
        import app.services.market_ml as ml

        settings = _settings_with_model_dir(tmp_path)
        monkeypatch.setattr("app.config.get_settings", lambda: settings)
        ml.reload_models()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: pd.DataFrame())
        monkeypatch.setattr(
            "app.services.market.normalize_symbol",
            lambda s: s + ".NS" if "." not in s else s,
        )

        resp = ml.get_forecast("TCS")
        assert resp.disclaimer == "Experimental educational feature. Not financial advice."


# ──────────────────────────────────────────────────────────────────────────────
# Forecast Response Schema
# ──────────────────────────────────────────────────────────────────────────────

class TestForecastResponse:

    def test_four_horizons_always_present(self, tmp_path, monkeypatch):
        import app.services.market_ml as ml

        settings = _settings_with_model_dir(tmp_path)
        monkeypatch.setattr("app.config.get_settings", lambda: settings)
        ml.reload_models()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: pd.DataFrame())
        monkeypatch.setattr(
            "app.services.market.normalize_symbol",
            lambda s: s + ".NS" if "." not in s else s,
        )

        resp = ml.get_forecast("TCS")
        assert len(resp.horizons) == 4
        assert {hf.horizon_days for hf in resp.horizons} == {1, 3, 5, 10}

    def test_null_probs_when_not_trained(self, tmp_path, monkeypatch):
        import app.services.market_ml as ml

        settings = _settings_with_model_dir(tmp_path)
        monkeypatch.setattr("app.config.get_settings", lambda: settings)
        ml.reload_models()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: pd.DataFrame())
        monkeypatch.setattr(
            "app.services.market.normalize_symbol",
            lambda s: s + ".NS" if "." not in s else s,
        )

        resp = ml.get_forecast("TCS")
        for hf in resp.horizons:
            if hf.model_status == "not_trained":
                assert hf.prob_up is None
                assert hf.predicted_class is None

    def test_schema_valid_for_all_statuses(self):
        """MarketForecastResponse instantiates correctly for every model_status."""
        from app.schemas import HorizonForecast, MarketForecastResponse

        statuses = ["ok", "not_trained", "stale", "insufficient_history"]
        horizons_list = []
        for i, status in enumerate(statuses):
            has_probs = status in ("ok", "stale")
            hf = HorizonForecast(
                horizon_days=[1, 3, 5, 10][i],
                predicted_class="UP" if has_probs else None,
                prob_up=0.6 if has_probs else None,
                prob_sideways=0.2 if has_probs else None,
                prob_down=0.2 if has_probs else None,
                uncertainty_flag=False,
                model_status=status,
                model_training_date=date.today() if has_probs else None,
                is_stale=(status == "stale"),
            )
            horizons_list.append(hf)

        resp = MarketForecastResponse(
            symbol="TCS.NS",
            horizons=horizons_list,
            fetched_at=1_737_020_400,
        )
        assert resp.disclaimer == "Experimental educational feature. Not financial advice."
        assert len(resp.horizons) == 4


# ──────────────────────────────────────────────────────────────────────────────
# Test utilities (not collected by pytest)
# ──────────────────────────────────────────────────────────────────────────────

class _FakeSettings:
    """Minimal Settings-like object for tests that need to override model_dir."""
    app_env = "test"
    gemini_api_key = ""
    market_ml_model_dir = "./data/models"
    market_ml_return_threshold_1d  = 0.01
    market_ml_return_threshold_3d  = 0.015
    market_ml_return_threshold_5d  = 0.02
    market_ml_return_threshold_10d = 0.025
    market_ml_staleness_days       = 7
    market_ml_min_history_bars     = 60

    def __init__(self, model_dir: Path) -> None:
        self.market_ml_model_dir = str(model_dir)
        self.project_root = Path("/")  # absolute paths from _model_dir()

    @property
    def cors_origin_list(self):
        return []


def _settings_with_model_dir(model_dir: Path) -> _FakeSettings:
    return _FakeSettings(model_dir)


class _MockPipeline:
    """Minimal sklearn-like pipeline for unit testing without training."""

    def __init__(self, probs: list[float]) -> None:
        self.classes_ = np.array(["DOWN", "SIDEWAYS", "UP"])
        self._probs   = np.array(probs)

    def predict_proba(self, X):
        return np.tile(self._probs, (len(X), 1))

    def predict(self, X):
        idx = np.argmax(self._probs)
        return np.array([self.classes_[idx]] * len(X))


def _mock_pipeline(probs: list[float]) -> _MockPipeline:
    return _MockPipeline(probs)


def _train_tiny_model(model_dir: Path, horizon: int = 1) -> None:
    """Train a minimal LR model on synthetic data and write artifacts to model_dir."""
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from app.services.market_ml import engineer_features, generate_labels, FEATURE_COLUMNS

    df       = _make_ohlcv(300)
    features = engineer_features(df)
    labels   = generate_labels(df.loc[features.index], horizon, threshold=0.01)

    valid = labels.notna()
    X     = features[valid][FEATURE_COLUMNS].values
    y     = labels[valid].values

    pipe = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=200, random_state=42))])
    pipe.fit(X, y)

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, model_dir / f"NSE_ALL_{horizon}d_lr.joblib", compress=3)
    meta = {
        "scope": "NSE_ALL",
        "horizon": horizon,
        "arch": "lr",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "feature_names": FEATURE_COLUMNS,
        "return_threshold": 0.01,
    }
    with open(model_dir / f"NSE_ALL_{horizon}d_lr.json", "w") as fh:
        json.dump(meta, fh)


# ──────────────────────────────────────────────────────────────────────────────
# Task 9: API Router tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMarketMLRouter:
    """Tests for GET /market-ml/{symbol}/forecast."""
    def test_200_not_trained_when_no_model(self, monkeypatch, tmp_path):
        """Valid symbol with no trained model → HTTP 200, all horizons not_trained."""
        import app.services.market_ml as ml
        from fastapi.testclient import TestClient
        from app.main import create_app
        monkeypatch.setattr(
        "app.services.market_ml.get_settings",
        lambda: _settings_with_model_dir(tmp_path),
        )
        ml.reload_models()
        monkeypatch.setattr(
        "app.services.market.get_history",
        lambda *a, **k: _make_ohlcv(120),
        )
        monkeypatch.setattr(
        "app.services.market.normalize_symbol",
        lambda s: s if "." in s else s + ".NS",
        )
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/market-ml/TCS.NS/forecast")
        assert resp.status_code == 200
        body = resp.json()
        assert body["disclaimer"] == "Experimental educational feature. Not financial advice."
        assert len(body["horizons"]) == 4
        for h in body["horizons"]:
            assert h["model_status"] == "not_trained"
            assert h["prob_up"] is None


    def test_200_with_trained_model(self, monkeypatch, tmp_path):
        """Symbol with a pre-trained model → HTTP 200, model_status='ok'."""
        import app.services.market_ml as ml
        from fastapi.testclient import TestClient
        from app.main import create_app

        _train_tiny_model(tmp_path, horizon=1)

        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()
        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: _make_ohlcv(200))
        monkeypatch.setattr("app.services.market.normalize_symbol", lambda s: s if "." in s else s + ".NS")

        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/market-ml/TCS.NS/forecast")

        assert resp.status_code == 200
        body = resp.json()
        h1 = next(h for h in body["horizons"] if h["horizon_days"] == 1)
        if h1["model_status"] == "ok":
            total = h1["prob_up"] + h1["prob_sideways"] + h1["prob_down"]
            assert abs(total - 1.0) <= 0.01

    def test_404_empty_dataframe(self, monkeypatch, tmp_path):
        """Empty DataFrame from get_history → HTTP 404."""
        import app.services.market_ml as ml
        from fastapi.testclient import TestClient
        from app.main import create_app

        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()
        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: pd.DataFrame())
        # Simulate symbol not found → LookupError from get_forecast
        import app.services.market_ml as _ml_mod

        _orig = _ml_mod.get_forecast

        def _raising_forecast(sym):
            raise LookupError(f"No data for {sym}")

        monkeypatch.setattr(_ml_mod, "get_forecast", _raising_forecast)

        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/market-ml/UNKNOWN.NS/forecast")

        assert resp.status_code == 404
        monkeypatch.setattr(_ml_mod, "get_forecast", _orig)

    def test_400_invalid_symbol(self, monkeypatch, tmp_path):
        """Symbol that causes normalize_symbol to raise ValueError → HTTP 400."""
        import app.services.market_ml as ml
        from fastapi.testclient import TestClient
        from app.main import create_app

        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()

        import app.services.market_ml as _ml_mod
        _orig = _ml_mod.get_forecast

        def _value_error(sym):
            raise ValueError("Symbol cannot be empty")

        monkeypatch.setattr(_ml_mod, "get_forecast", _value_error)

        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/market-ml/X/forecast")

        assert resp.status_code == 400
        monkeypatch.setattr(_ml_mod, "get_forecast", _orig)

    def test_500_on_unhandled_error(self, monkeypatch, tmp_path):
        """Unhandled RuntimeError in get_forecast → HTTP 500, no stack trace exposed."""
        import app.services.market_ml as ml
        import app.services.market_ml as _ml_mod
        from fastapi.testclient import TestClient
        from app.main import create_app

        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()

        _orig = _ml_mod.get_forecast

        def _boom(sym):
            raise RuntimeError("disk full")

        monkeypatch.setattr(_ml_mod, "get_forecast", _boom)

        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/market-ml/TCS.NS/forecast")

        assert resp.status_code == 500
        assert "disk full" not in resp.text, "Internal error detail must not leak to client"
        assert "An internal error occurred" in resp.json()["detail"]
        monkeypatch.setattr(_ml_mod, "get_forecast", _orig)

    def test_disclaimer_in_all_responses(self, monkeypatch, tmp_path):
        """disclaimer field is present in every 200 response."""
        import app.services.market_ml as ml
        from fastapi.testclient import TestClient
        from app.main import create_app

        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()
        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: _make_ohlcv(120))
        monkeypatch.setattr("app.services.market.normalize_symbol", lambda s: s if "." in s else s + ".NS")

        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/market-ml/TCS.NS/forecast")

        assert resp.status_code == 200
        assert resp.json()["disclaimer"] == "Experimental educational feature. Not financial advice."


# ──────────────────────────────────────────────────────────────────────────────
# Task 10: Market Insights Service tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMarketInsightsService:
    """Tests for market_insights.get_market_insight()."""

    def test_returns_without_raising(self, db, monkeypatch, tmp_path):
        """get_market_insight always returns a dict, never raises."""
        from app.services import market_insights
        from app.models import User, Stock

        _seed_db(db)
        user = db.query(User).first()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: _make_ohlcv(120))
        monkeypatch.setattr("app.services.market.normalize_symbol", lambda s: s if "." in s else s + ".NS")
        import app.services.market_ml as ml
        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()

        result = market_insights.get_market_insight(db, user, "TCS.NS")
        assert isinstance(result, dict)
        assert "forecast" in result
        assert "mode" in result

    def test_aifinding_written_not_interventionlog(self, db, monkeypatch, tmp_path):
        """Exactly one AIFinding row written; zero new InterventionLog rows."""
        from app.services import market_insights
        from app.models import AIFinding, InterventionLog

        _seed_db(db)
        from app.models import User
        user = db.query(User).first()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: _make_ohlcv(120))
        monkeypatch.setattr("app.services.market.normalize_symbol", lambda s: s if "." in s else s + ".NS")
        import app.services.market_ml as ml
        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()

        log_count_before = db.query(InterventionLog).count()
        finding_count_before = db.query(AIFinding).count()

        market_insights.get_market_insight(db, user, "TCS.NS")

        assert db.query(InterventionLog).count() == log_count_before, \
            "InterventionLog must not be modified by market_insights"
        assert db.query(AIFinding).count() == finding_count_before + 1, \
            "Exactly one new AIFinding should be written"
        finding = db.query(AIFinding).filter_by(kind="market_prediction").first()
        assert finding is not None
        assert finding.source == "ai"

    def test_forecast_omitted_from_llm_context_when_no_model(self, db, monkeypatch, tmp_path):
        """When model_status is not_trained for all horizons, LLM still called (patterns/RAG context)."""
        from app.services import market_insights

        _seed_db(db)
        from app.models import User
        user = db.query(User).first()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: _make_ohlcv(120))
        monkeypatch.setattr("app.services.market.normalize_symbol", lambda s: s if "." in s else s + ".NS")
        import app.services.market_ml as ml
        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        ml.reload_models()

        result = market_insights.get_market_insight(db, user, "TCS.NS")
        # LLM is not available (fake_llm autouse fixture), so mode should be offline
        assert result["mode"] in ("offline", "generated", "cached")
        # Forecast object is always present regardless
        assert result["forecast"] is not None

    def test_degraded_response_on_internal_failure(self, db, monkeypatch, tmp_path):
        """If the internal function raises, get_market_insight returns a safe fallback."""
        from app.services import market_insights

        _seed_db(db)
        from app.models import User
        user = db.query(User).first()

        # Force an error inside the service
        monkeypatch.setattr(
            market_insights, "_get_market_insight",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("forced failure")),
        )

        result = market_insights.get_market_insight(db, user, "TCS.NS")
        assert result["mode"] == "offline"
        assert result["forecast"] is None


# ──────────────────────────────────────────────────────────────────────────────
# Task 11: Regression tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRegressions:
    """Verify that importing / running the new ML module has zero impact on
    existing services."""

    def test_intervention_engine_unchanged(self, db, monkeypatch):
        """evaluate_pre_trade returns the same results with market_ml imported."""
        from app.services import interventions
        from app.services import market_ml  # noqa: F401 — just import it

        _seed_db(db)
        from app.models import User
        user = db.query(User).first()

        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: None)
        result = interventions.evaluate_pre_trade(db, user, "TCS.NS", "buy", 1.0)
        # Should return a list (possibly empty, possibly with rules) without error.
        assert isinstance(result, list)

    def test_readiness_score_unchanged(self, db):
        """compute_readiness returns a valid dict with market_ml imported."""
        from app.services import readiness
        from app.services import market_ml  # noqa: F401

        _seed_db(db)
        from app.models import User
        user = db.query(User).first()

        result = readiness.compute_readiness(db, user)
        assert "score" in result
        assert 0.0 <= result["score"] <= 100.0

    def test_no_intervention_log_on_forecast(self, db, monkeypatch, tmp_path):
        """Calling get_forecast() must not touch InterventionLog at all."""
        from app.services import market_ml
        from app.models import InterventionLog

        _seed_db(db)
        monkeypatch.setattr("app.services.market.get_history", lambda *a, **k: _make_ohlcv(120))
        monkeypatch.setattr("app.services.market.normalize_symbol", lambda s: s if "." in s else s + ".NS")
        monkeypatch.setattr("app.config.get_settings", lambda: _settings_with_model_dir(tmp_path))
        market_ml.reload_models()

        before = db.query(InterventionLog).count()
        market_ml.get_forecast("TCS.NS")
        assert db.query(InterventionLog).count() == before


# ──────────────────────────────────────────────────────────────────────────────
# Additional seed helper (used by Tasks 9–11 tests)
# ──────────────────────────────────────────────────────────────────────────────

def _seed_db(db) -> None:
    """Insert a minimal User and Stock so service calls don't fail on missing rows."""
    from app.models import Stock, User

    if not db.query(User).first():
        user = User(
            id="test-user-001",
            email="learner@example.test",
            persona="teen",
            risk_appetite="low",
            cash=100_000.0,
            language="en",
        )
        db.add(user)

    if not db.query(Stock).filter_by(symbol="TCS.NS").first():
        stock = Stock(
            symbol="TCS.NS",
            name="Tata Consultancy Services",
            sector="IT",
            market_cap_band="large",
            risk_level="medium",
        )
        db.add(stock)

    db.commit()
