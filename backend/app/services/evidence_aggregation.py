"""Pure aggregation helpers for auditable readiness evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DimensionEstimate:
    score: float
    evidence_count: int
    confidence: float
    sufficient: bool
    evidence: tuple[str, ...] = field(default_factory=tuple)


def _valid(estimate: DimensionEstimate | None) -> bool:
    if estimate is None:
        return False
    try:
        return (
            math.isfinite(float(estimate.score))
            and 0 <= float(estimate.score) <= 100
            and math.isfinite(float(estimate.confidence))
            and 0 <= float(estimate.confidence) <= 1
            and estimate.evidence_count >= 0
        )
    except (TypeError, ValueError, OverflowError):
        return False


def aggregate_dimension(
    deterministic: DimensionEstimate | None,
    ml: DimensionEstimate | None,
    *,
    ml_weight: float = 0.5,
    blend_enabled: bool = True,
    ml_exclusion_reason: str = "ml_evidence_missing_or_invalid",
) -> dict[str, Any]:
    """Blend only sufficient, valid estimates; never turn missing ML into zero."""
    if not math.isfinite(float(ml_weight)) or not 0 <= ml_weight <= 1:
        raise ValueError("ml_weight must be between 0 and 1")
    det_ok = _valid(deterministic)
    ml_ok = _valid(ml)
    det_usable = det_ok and deterministic.sufficient
    ml_usable = ml_ok and ml.sufficient
    det_displayable = det_ok

    blend = det_usable and ml_usable and blend_enabled
    if blend:
        score = (float(deterministic.score) * (1 - ml_weight)
                 + float(ml.score) * ml_weight)
        source = "blended"
        reason = None
    elif det_displayable:
        score = float(deterministic.score)
        source = "deterministic"
        if not deterministic.sufficient:
            reason = "deterministic_estimate_provisional"
        else:
            reason = "ml_evidence_insufficient" if ml_ok else ml_exclusion_reason
    else:
        score = None
        source = "none"
        reason = "no_sufficient_valid_estimate"

    contributions = []
    for name, estimate, usable in (("deterministic", deterministic, det_usable), ("ml", ml, ml_usable)):
        if estimate is None:
            contributions.append({"source": name, "included": False, "reason": "missing"})
        elif not _valid(estimate):
            contributions.append({"source": name, "included": False, "reason": "invalid"})
        elif (not estimate.sufficient
              or (name == "ml" and (not blend_enabled or not det_usable))):
            provisional = name == "deterministic" and det_displayable
            if name == "ml" and not blend_enabled:
                excluded_reason = "blending_not_configured"
            elif name == "ml" and not det_usable:
                excluded_reason = "deterministic_evidence_insufficient"
            else:
                excluded_reason = "provisional_estimate" if provisional else "insufficient_evidence"
            contributions.append({
                "source": name,
                "included": provisional,
                "used_for_blending": False,
                "reason": excluded_reason,
                "score": round(float(estimate.score), 2) if provisional else None,
                "confidence": round(float(estimate.confidence), 4),
                "evidence_count": estimate.evidence_count,
                "evidence": list(estimate.evidence),
            })
        else:
            contributions.append({
                "source": name,
                "included": usable,
                "used_for_blending": blend,
                "score": round(float(estimate.score), 2),
                "confidence": round(float(estimate.confidence), 4),
                "evidence_count": estimate.evidence_count,
                "evidence": list(estimate.evidence),
            })

    return {
        "score": round(max(0.0, min(score, 100.0)), 2) if score is not None else None,
        "source": source,
        "fallback_reason": reason,
        "contributions": contributions,
        "confidence": max(
            [float(e.confidence) for e, valid in ((deterministic, det_ok), (ml, ml_ok))
             if e is not None and valid],
            default=0.0,
        ),
        # ML evidence can only affect the score as part of a valid blend. A
        # sufficient ML-only estimate must not make a deterministic fallback
        # look evidence-sufficient.
        "sufficient": bool(score is not None and (det_usable or blend)),
    }


def weighted_score(
    dimensions: dict[str, dict[str, Any]], weights: dict[str, float]
) -> float | None:
    """Weight only observed estimates and renormalize their configured weights."""
    if set(weights) != set(dimensions):
        raise ValueError("weights and dimensions must have the same keys")
    if any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("weights must be finite and non-negative")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-8):
        raise ValueError("weights must sum to 1")
    observed = [
        (float(dimensions[name]["score"]), weight)
        for name, weight in weights.items()
        if dimensions[name].get("score") is not None and weight > 0
    ]
    total_weight = sum(weight for _, weight in observed)
    if total_weight == 0:
        return None
    return round(sum(score * weight for score, weight in observed) / total_weight, 1)
