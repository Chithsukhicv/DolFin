"""Market Movement Predictor — feature engineering, label generation, inference.

This module is the runtime half of the ML pipeline.  Everything here is called
on the live API path; the training half lives in market_ml_training.py and is
never imported from here.

Design constraints
------------------
* All indicator math uses pandas / NumPy only — no ta-lib or pandas-ta.
* Every feature at bar t uses only data from bars ≤ t (no look-ahead).
* Models are loaded lazily on the first prediction request and held in a
  module-level dict so they are never re-read from disk on subsequent calls.
* The public entry point (get_forecast) never raises — it always returns a
  MarketForecastResponse with an appropriate model_status per horizon.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import get_settings
from app.schemas import HorizonForecast, MarketForecastResponse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HORIZONS: list[int] = [1, 3, 5, 10]
SYMBOL_SCOPE: str = "NSE_ALL"

# Exact feature column names — must match between training and inference.
FEATURE_COLUMNS: list[str] = [
    "ret_1d", "ret_3d", "ret_5d", "ret_10d",
    "sma_5", "sma_10", "sma_20", "sma_50",
    "ema_12", "ema_26",
    "macd", "macd_signal", "macd_hist",
    "rsi_14",
    "vol_5", "vol_10", "vol_20",
    "atr_14",
    "vol_chg", "rel_vol",
    "roc_5", "roc_10", "roc_20",
]

# ---------------------------------------------------------------------------
# Module-level model cache  {(scope, horizon): (pipeline, metadata) | None}
# ---------------------------------------------------------------------------
_model_cache: dict[tuple[str, int], tuple[Any, dict] | None] = {}


def reload_models() -> None:
    """Clear the in-memory model cache.  Used in tests to force a fresh load."""
    _model_cache.clear()


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 23 feature columns from a raw OHLCV DataFrame.

    Parameters
    ----------
    df:
        pandas DataFrame with columns Open, High, Low, Close, Volume and a
        DatetimeIndex, as returned by market_service.get_history().

    Returns
    -------
    A new DataFrame containing only FEATURE_COLUMNS.  Rows where any OHLCV
    input or derived feature is NaN / non-finite are dropped.  An empty
    DataFrame is returned (without raising) when the input is empty or too
    short for any rolling window.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(df.columns):
        log.warning("engineer_features: missing columns %s", required - set(df.columns))
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    # Work on a sorted copy; drop exact duplicate index entries.
    d = df[list(required)].copy()
    d = d[~d.index.duplicated(keep="last")]
    d = d.sort_index()

    # Drop rows with NaN/Inf in the raw OHLCV fields.
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required))

    if d.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    close = d["Close"]
    high  = d["High"]
    low   = d["Low"]
    vol   = d["Volume"]

    out = pd.DataFrame(index=d.index)

    # --- Returns ---
    out["ret_1d"]  = close.pct_change(1)
    out["ret_3d"]  = close.pct_change(3)
    out["ret_5d"]  = close.pct_change(5)
    out["ret_10d"] = close.pct_change(10)

    # --- Simple moving averages ---
    out["sma_5"]  = close.rolling(5).mean()
    out["sma_10"] = close.rolling(10).mean()
    out["sma_20"] = close.rolling(20).mean()
    out["sma_50"] = close.rolling(50).mean()

    # --- Exponential moving averages ---
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    out["ema_12"] = ema_12
    out["ema_26"] = ema_26

    # --- MACD ---
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    out["macd"]        = macd
    out["macd_signal"] = macd_signal
    out["macd_hist"]   = macd - macd_signal

    # --- RSI (Wilder smoothing) ---
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi_14"] = (100 - 100 / (1 + rs)).clip(0, 100)

    # --- Rolling volatility of log returns ---
    log_ret = np.log(close / close.shift(1))
    out["vol_5"]  = log_ret.rolling(5).std()
    out["vol_10"] = log_ret.rolling(10).std()
    out["vol_20"] = log_ret.rolling(20).std()

    # --- Average True Range (Wilder) ---
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    # --- Volume features ---
    out["vol_chg"] = vol.pct_change(1)
    vol_ma20 = vol.rolling(20).mean()
    out["rel_vol"] = vol / vol_ma20.replace(0, np.nan)

    # --- Rate of change (momentum) ---
    out["roc_5"]  = close.pct_change(5)
    out["roc_10"] = close.pct_change(10)
    out["roc_20"] = close.pct_change(20)

    # Drop rows where any feature is NaN / Inf.
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS)

    return out[FEATURE_COLUMNS]


# ---------------------------------------------------------------------------
# Label generation
# ---------------------------------------------------------------------------

def _threshold_for_horizon(horizon: int) -> float:
    """Read the configured return threshold for a given horizon from settings."""
    s = get_settings()
    mapping = {
        1:  s.market_ml_return_threshold_1d,
        3:  s.market_ml_return_threshold_3d,
        5:  s.market_ml_return_threshold_5d,
        10: s.market_ml_return_threshold_10d,
    }
    if horizon not in mapping:
        raise ValueError(f"Unsupported horizon {horizon!r}; must be one of {list(mapping)}")
    return mapping[horizon]


def generate_labels(
    df: pd.DataFrame,
    horizon: int,
    threshold: float,
) -> pd.Series:
    """Compute UP / SIDEWAYS / DOWN forward-return labels.

    Parameters
    ----------
    df:
        DataFrame with at least a Close column (same index as the feature matrix).
    horizon:
        Number of trading days forward to measure the return.
    threshold:
        Minimum absolute fractional return to classify as UP or DOWN.
        A return within [-threshold, +threshold] is SIDEWAYS.

    Returns
    -------
    pd.Series of str ('UP', 'SIDEWAYS', 'DOWN') aligned to df's index.
    The last ``horizon`` rows are NaN because forward Close is unavailable.
    """
    close = df["Close"]
    fwd_return = (close.shift(-horizon) - close) / close

    labels = pd.Series(index=df.index, dtype=object)
    labels[fwd_return > threshold]   = "UP"
    labels[fwd_return < -threshold]  = "DOWN"
    mask_sideways = (fwd_return >= -threshold) & (fwd_return <= threshold)
    labels[mask_sideways] = "SIDEWAYS"
    # The last `horizon` rows have NaN fwd_return — leave them as NaN.
    return labels


# ---------------------------------------------------------------------------
# Model artifact helpers
# ---------------------------------------------------------------------------

def _model_dir() -> Path:
    s = get_settings()
    p = (s.project_root / s.market_ml_model_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _artifact_paths(scope: str, horizon: int) -> tuple[list[Path], list[Path]]:
    """Return (joblib_paths, json_paths) matching the glob pattern."""
    d = _model_dir()
    pattern = f"{scope}_{horizon}d_*.joblib"
    joblibfiles = sorted(d.glob(pattern))
    jsonfiles   = [p.with_suffix(".json") for p in joblibfiles]
    return joblibfiles, jsonfiles


def _load_model(scope: str, horizon: int) -> tuple[Any, dict] | tuple[None, None]:
    """Load pipeline + metadata from disk on first call; cache the result.

    Returns (pipeline, metadata_dict) or (None, None) if no artifact exists.
    Failures during load are logged and treated as missing.
    """
    key = (scope, horizon)
    if key in _model_cache:
        return _model_cache[key]  # type: ignore[return-value]

    joblibfiles, jsonfiles = _artifact_paths(scope, horizon)
    if not joblibfiles:
        _model_cache[key] = None
        return None, None

    joblib_path = joblibfiles[0]
    json_path   = jsonfiles[0]

    try:
        import joblib  # always available — listed in requirements.txt
        pipeline = joblib.load(joblib_path)
        meta: dict = {}
        if json_path.exists():
            with open(json_path, encoding="utf-8") as fh:
                meta = json.load(fh)
        result = (pipeline, meta)
        _model_cache[key] = result
        return result
    except Exception as exc:
        log.error("Failed to load model artifact %s: %s", joblib_path, exc)
        _model_cache[key] = None
        return None, None


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

def _is_stale(meta: dict) -> bool:
    """True when the model's training_date is older than the staleness threshold."""
    training_date_str = meta.get("training_date")
    if not training_date_str:
        return False
    try:
        td = datetime.fromisoformat(training_date_str.replace("Z", "+00:00"))
        if td.tzinfo is None:
            td = td.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - td).days
        return age_days > get_settings().market_ml_staleness_days
    except Exception:
        return False


def _predict_horizon(
    features: pd.DataFrame,
    scope: str,
    horizon: int,
) -> HorizonForecast:
    """Run a single horizon's model and return its HorizonForecast."""
    pipeline, meta = _load_model(scope, horizon)

    if pipeline is None:
        return HorizonForecast(
            horizon_days=horizon,
            predicted_class=None,
            prob_up=None,
            prob_sideways=None,
            prob_down=None,
            uncertainty_flag=False,
            model_status="not_trained",
            model_training_date=None,
            is_stale=False,
        )

    if features.empty or len(features) < 1:
        return HorizonForecast(
            horizon_days=horizon,
            predicted_class=None,
            prob_up=None,
            prob_sideways=None,
            prob_down=None,
            uncertainty_flag=False,
            model_status="insufficient_history",
            model_training_date=None,
            is_stale=False,
        )

    stale = _is_stale(meta)
    status = "stale" if stale else "ok"

    # Training date for the response
    td_str = meta.get("training_date")
    from datetime import date
    try:
        model_training_date = datetime.fromisoformat(
            td_str.replace("Z", "+00:00")
        ).date() if td_str else None
    except Exception:
        model_training_date = None

    # Inference on the last available bar
    X = features[FEATURE_COLUMNS].iloc[-1:]

    try:
        proba = pipeline.predict_proba(X)[0]
    except Exception as exc:
        log.error("predict_proba failed for scope=%s horizon=%d: %s", scope, horizon, exc)
        return HorizonForecast(
            horizon_days=horizon,
            predicted_class=None,
            prob_up=None,
            prob_sideways=None,
            prob_down=None,
            uncertainty_flag=False,
            model_status="insufficient_history",
            model_training_date=model_training_date,
            is_stale=stale,
        )

    # Map class order from pipeline.classes_ to named probs
    classes = list(pipeline.classes_)
    prob_map: dict[str, float] = {c: float(proba[i]) for i, c in enumerate(classes)}

    p_up   = prob_map.get("UP",       0.0)
    p_side = prob_map.get("SIDEWAYS", 0.0)
    p_down = prob_map.get("DOWN",     0.0)

    # Normalise if the sum is slightly off (floating-point)
    total = p_up + p_side + p_down
    if total > 0 and not (0.99 <= total <= 1.01):
        p_up   /= total
        p_side /= total
        p_down /= total

    predicted_class = max(prob_map, key=prob_map.get)  # type: ignore[arg-type]
    uncertainty = max(p_up, p_side, p_down) < 0.45

    return HorizonForecast(
        horizon_days=horizon,
        predicted_class=predicted_class,  # type: ignore[arg-type]
        prob_up=round(p_up, 4),
        prob_sideways=round(p_side, 4),
        prob_down=round(p_down, 4),
        uncertainty_flag=uncertainty,
        model_status=status,  # type: ignore[arg-type]
        model_training_date=model_training_date,
        is_stale=stale,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_forecast(symbol: str) -> MarketForecastResponse:
    """Fetch OHLCV history, engineer features, run all four horizon models.

    Never raises.  All error states are communicated via model_status in the
    returned HorizonForecast items.
    """
    from app.services import market as market_service

    try:
        norm = market_service.normalize_symbol(symbol)
    except ValueError:
        # Let the router convert this to HTTP 400.
        raise

    features = pd.DataFrame(columns=FEATURE_COLUMNS)
    try:
        df = market_service.get_history(norm, period="6mo", interval="1d")
        if df is not None and not df.empty:
            features = engineer_features(df)
    except Exception as exc:
        log.warning("get_history failed for %s: %s", norm, exc)

    min_bars = get_settings().market_ml_min_history_bars
    use_features = features if len(features) >= min_bars else pd.DataFrame(columns=FEATURE_COLUMNS)

    horizons_out: list[HorizonForecast] = []
    for h in HORIZONS:
        hf = _predict_horizon(use_features, norm, h)
        horizons_out.append(hf)

    return MarketForecastResponse(
        symbol=norm,
        horizons=horizons_out,
        fetched_at=int(time.time()),
    )
