"""Per-user longitudinal anomaly analysis.

This is intentionally advisory. A statistical outlier is unusual, not
necessarily harmful, and is never converted into a readiness dimension score.
The user-specific baseline avoids cross-user leakage and no external model or
network service is involved.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import median

MIN_TRADE_DAYS = 6
MIN_TRADES = 20
ROBUST_Z_THRESHOLD = 3.5


def _robust_z(value: float, baseline: list[float]) -> float:
    center = median(baseline)
    mad = median([abs(sample - center) for sample in baseline])
    # A zero MAD is common for small integer counts. The floor keeps the
    # statistic bounded without making a single extra trade look dangerous.
    scale = max(1.4826 * mad, math.sqrt(max(center, 1.0)))
    return (value - center) / scale


def analyse_trade_anomalies(evidence: dict) -> dict:
    """Flag unusually high session frequency only after a personal baseline.

    At least six trade days and twenty trades are required. A candidate day is
    compared with earlier days only. The result describes novelty and cannot
    lower or raise numeric readiness.
    """
    today = date.fromisoformat(evidence.get("today", date.today().isoformat()))
    cutoff = today - timedelta(days=59)
    daily = []
    for row in evidence.get("daily_trade_activity", []):
        try:
            day = date.fromisoformat(row["date"])
            if cutoff <= day <= today:
                daily.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    count = int(evidence.get("recent_trade_count", evidence.get("trade_count", 0)) or 0)
    if count < MIN_TRADES or len(daily) < MIN_TRADE_DAYS:
        return {
            "status": "insufficient_evidence",
            "method": "per_user_robust_frequency_baseline",
            "minimum_evidence": {"trades": MIN_TRADES, "trade_days": MIN_TRADE_DAYS},
            "observed": {"trades": count, "trade_days": len(daily)},
            "findings": [],
            "affects_score": False,
            "reason": "not_enough_longitudinal_trade_history",
        }

    values = [float(row.get("trade_count", 0)) for row in daily]
    findings = []
    # Require five previous trade days; assess only the most recent day so a
    # historical spike does not remain a permanent current warning.
    prior = values[:-1]
    latest = values[-1]
    if len(prior) >= 5:
        z = _robust_z(latest, prior)
        if z >= ROBUST_Z_THRESHOLD:
            findings.append({
                "kind": "unusual_trade_frequency",
                "description": "Recent trade count is unusual relative to this learner's own history.",
                "observed": latest,
                "baseline_median": median(prior),
                "robust_z": round(z, 3),
                "interpretation": "unusual_not_necessarily_risky",
            })
    return {
        "status": "analysed",
        "method": "per_user_robust_frequency_baseline",
        "minimum_evidence": {"trades": MIN_TRADES, "trade_days": MIN_TRADE_DAYS},
        "observed": {"trades": count, "trade_days": len(daily)},
        "findings": findings,
        "affects_score": False,
        "reason": None,
    }
