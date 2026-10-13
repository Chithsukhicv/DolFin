"""Readiness Score V2: reproducible scoring with explicit evidence sufficiency.

The score remains a deterministic 0–100 weighted estimate. It is withheld until
the learner has a multi-day simulator record, while dimension evidence and
practice achievements remain visible during cold start. Statistical anomaly
findings are advisory and do not provide a numeric readiness estimate.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Goal,
    Holding,
    InterventionLog,
    QuizAttempt,
    ReadinessSnapshot,
    Transaction,
    User,
)
from app.services import behavioral_ml, portfolio as portfolio_service
from app.services.behavioral_evidence import build_behavioral_evidence
from app.services.evidence_aggregation import DimensionEstimate, aggregate_dimension, weighted_score

GRADUATION_THRESHOLD = 80.0
FULL_CONFIDENCE_TRADES = 12
FULL_CONFIDENCE_HOLDINGS = 8
FULL_CONFIDENCE_TRADE_DAYS = 5
MIN_GRADUATION_HISTORY_DAYS = 14
BEGINNER_ANCHOR = 8.0
AUTONOMY_PRIOR_TRADES = 6.0
AUTONOMY_PRIOR_CLEAN_RATE = 0.5
QUIZ_PASS_BONUS = 6.0
QUIZ_BONUS_CAP = 24.0


def readiness_weights() -> dict[str, float]:
    settings = get_settings()
    return {
        "diversification": settings.readiness_weight_diversification,
        "discipline": settings.readiness_weight_discipline,
        "goal_alignment": settings.readiness_weight_goal_alignment,
        "autonomy": settings.readiness_weight_autonomy,
        "consistency": settings.readiness_weight_consistency,
        "engagement": settings.readiness_weight_engagement,
    }


def _confidence(observed: float, needed: float) -> float:
    return max(0.0, min(observed / needed, 1.0)) if needed > 0 else 1.0


def _shrink(score: float, confidence: float, anchor: float = BEGINNER_ANCHOR) -> float:
    return anchor + (score - anchor) * confidence


def _diversification_subscore(snapshot: dict, db: Session | None = None, user: User | None = None) -> float | None:
    holdings = snapshot["holdings"]
    market_value = snapshot["market_value"]
    if not holdings or market_value <= 0:
        return None
    max_pos_pct = max(h["market_value"] / market_value for h in holdings)
    pos_penalty = max(0.0, max_pos_pct - 0.20) * 100
    sectors = snapshot.get("sector_allocation_pct", {})
    max_sector_pct = max(sectors.values()) / 100.0 if sectors else 0.0
    sector_penalty = max(0.0, max_sector_pct - 0.40) * 80
    score = 60 + min(len(sectors) * 8, 40) - pos_penalty - sector_penalty
    return max(0.0, min(score, 100.0))


def _quiz_bonus(db: Session, user: User) -> float:
    passed = (
        db.query(QuizAttempt.concept)
        .filter(QuizAttempt.user_id == user.id, QuizAttempt.passed.is_(True))
        .distinct()
        .count()
    )
    return min(passed * QUIZ_PASS_BONUS, QUIZ_BONUS_CAP)


def _discipline_subscore(db: Session, user: User) -> float | None:
    since = datetime.now(timezone.utc) - timedelta(days=60)
    logs = (
        db.query(InterventionLog)
        .filter(InterventionLog.user_id == user.id, InterventionLog.created_at >= since)
        .all()
    )
    txn_count = db.query(Transaction).filter_by(user_id=user.id).count()
    quiz_bonus = _quiz_bonus(db, user)
    if not logs and txn_count == 0:
        return min(quiz_bonus, 100.0) if quiz_bonus else None

    ignored = [row for row in logs if row.user_action == "ignored"]
    counts = Counter(row.rule_id for row in ignored)
    penalty = (
        counts.get("panic_sell", 0) * 20
        + counts.get("fomo", 0) * 10
        + counts.get("short_hold", 0) * 5
    )
    heeded = sum(row.user_action == "heeded" for row in logs)
    credit = min(heeded * 5, 30) + quiz_bonus
    # No warning observed is neutral, not a perfect discipline record.
    baseline = 70.0 if logs else 50.0
    return max(0.0, min(baseline + credit - penalty, 100.0))


def _goal_alignment_subscore(db: Session, user: User, snapshot: dict) -> float | None:
    goals = db.query(Goal).filter_by(user_id=user.id).all()
    txns = db.query(Transaction).filter_by(user_id=user.id).count()
    if not goals or txns == 0:
        return None
    avg_horizon = sum(goal.horizon_months for goal in goals) / len(goals)
    score = 70.0
    if avg_horizon >= 60 and txns > 30:
        score -= 25
    if avg_horizon < 12 and len(snapshot["holdings"]) > 5:
        score -= 15
    if 12 <= avg_horizon <= 60:
        score += 10
    return max(0.0, min(score, 100.0))


def _autonomy_subscore(db: Session, user: User) -> float | None:
    since = datetime.now(timezone.utc) - timedelta(days=60)
    txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id, Transaction.created_at >= since)
        .all()
    )
    if not txns:
        return None
    flagged = sum(
        any(item.get("severity") in ("warn", "critical") for item in (txn.interventions_fired or []))
        for txn in txns
    )
    clean = len(txns) - flagged
    return (clean + AUTONOMY_PRIOR_TRADES * AUTONOMY_PRIOR_CLEAN_RATE) / (
        len(txns) + AUTONOMY_PRIOR_TRADES
    ) * 100.0


def _consistency_score(evidence: dict) -> float | None:
    days = evidence["rolling_30_day_practice_days"]
    if days == 0:
        return None
    # A modest target of two meaningful days/week over a 30-day window.
    return min(days / 8.0 * 100.0, 100.0)


def _engagement_score(evidence: dict) -> float | None:
    days = evidence["practice_day_count"]
    if days == 0:
        return None
    # Engagement counts distinct verified practice dates, never trade volume.
    return min(days / 10.0 * 100.0, 100.0)


def _estimate(score: float | None, *, count: int, confidence: float,
              sufficient: bool, evidence: tuple[str, ...]) -> DimensionEstimate | None:
    if score is None:
        return None
    return DimensionEstimate(
        score=max(0.0, min(float(score), 100.0)),
        evidence_count=max(0, int(count)),
        confidence=max(0.0, min(float(confidence), 1.0)),
        sufficient=sufficient,
        evidence=evidence,
    )


def compute_readiness(db: Session, user: User) -> dict[str, Any]:
    snapshot = portfolio_service.portfolio_snapshot(db, user)
    evidence = build_behavioral_evidence(db, user)
    trade_count = evidence["trade_count"]
    trade_days = evidence["trade_day_count"]
    holdings_count = len(snapshot["holdings"])
    span_days = evidence["history_span_days"]

    recent_trade_count = evidence["recent_trade_count"]
    recent_trade_days = evidence["recent_trade_day_count"]
    trade_conf = _confidence(recent_trade_count, FULL_CONFIDENCE_TRADES)
    holding_conf = _confidence(holdings_count, FULL_CONFIDENCE_HOLDINGS)
    day_conf = _confidence(recent_trade_days, FULL_CONFIDENCE_TRADE_DAYS)
    span_conf = _confidence(
        evidence["recent_trade_history_span_days"], MIN_GRADUATION_HISTORY_DAYS
    )
    confidence = round(min(trade_conf, holding_conf, day_conf, span_conf), 2)
    enough_history = (
        recent_trade_count >= FULL_CONFIDENCE_TRADES
        and recent_trade_days >= FULL_CONFIDENCE_TRADE_DAYS
        and holdings_count >= FULL_CONFIDENCE_HOLDINGS
        and evidence["recent_trade_history_span_days"] >= MIN_GRADUATION_HISTORY_DAYS
    )

    raw_scores = {
        "diversification": _diversification_subscore(snapshot),
        "discipline": _discipline_subscore(db, user),
        "goal_alignment": _goal_alignment_subscore(db, user, snapshot),
        "autonomy": _autonomy_subscore(db, user),
        "consistency": _consistency_score(evidence),
        "engagement": _engagement_score(evidence),
    }
    behavior_sufficient = (
        recent_trade_count >= FULL_CONFIDENCE_TRADES
        and recent_trade_days >= FULL_CONFIDENCE_TRADE_DAYS
        and evidence["recent_trade_history_span_days"] >= MIN_GRADUATION_HISTORY_DAYS
    )
    consistency_sufficient = (
        evidence["rolling_30_day_practice_days"] >= 4
        and span_days >= MIN_GRADUATION_HISTORY_DAYS
    )
    settings = get_settings()
    blend_dimensions = {
        item.strip() for item in settings.readiness_ml_blend_dimensions.split(",") if item.strip()
    }
    dimensions: dict[str, dict] = {}
    for name, score in raw_scores.items():
        if name == "diversification":
            count = holdings_count
            sufficient = holdings_count >= FULL_CONFIDENCE_HOLDINGS
            conf = holding_conf
            facts = ("current_portfolio_allocation", "current_sector_spread")
        elif name in ("discipline", "goal_alignment", "autonomy"):
            count = trade_count
            sufficient = behavior_sufficient and (name != "goal_alignment" or score is not None)
            conf = min(trade_conf, day_conf, span_conf)
            facts = {
                "discipline": ("resolved_rule_outcomes", "distinct_passed_quiz_concepts"),
                "goal_alignment": ("user_goal_horizons", "trade_history"),
                "autonomy": ("warn_free_recent_trades", "trade_history"),
            }[name]
        else:
            count = evidence["practice_day_count"]
            sufficient = consistency_sufficient
            conf = _confidence(count, 8)
            facts = ("verified_distinct_utc_practice_dates", "rolling_30_day_window")

        ml_estimate = None  # The anomaly engine is not a readiness-label model.
        det_estimate = _estimate(
            score,
            count=count,
            confidence=conf,
            sufficient=sufficient,
            evidence=facts,
        )
        dimensions[name] = aggregate_dimension(
            det_estimate,
            ml_estimate,
            ml_weight=settings.readiness_ml_blend_weight,
            blend_enabled=name in blend_dimensions,
            ml_exclusion_reason="anomaly_output_is_not_a_readiness_estimate",
        )

    weights = readiness_weights()
    calculated_score = weighted_score(dimensions, weights)
    observed_weight = sum(
        weights[name] for name, value in dimensions.items() if value["score"] is not None
    )
    effective_weights = {
        name: round(weights[name] / observed_weight, 6)
        if enough_history and value["score"] is not None and observed_weight else 0.0
        for name, value in dimensions.items()
    }
    assessment_state = "assessable" if enough_history else "insufficient_evidence"
    score = calculated_score if enough_history else None

    # Graduation requires evidence for each core behavioural dimension as well
    # as the proposed score threshold. A missing goal is an unobserved signal.
    graduation_eligible = enough_history and all(
        dimensions[name]["sufficient"]
        for name in ("diversification", "discipline", "goal_alignment", "autonomy", "consistency")
    )
    if not enough_history:
        behaviour_state = "insufficient_evidence"
    elif (
        dimensions["discipline"]["score"] is not None
        and dimensions["discipline"]["score"] <= 35
    ) or (
        dimensions["autonomy"]["score"] is not None
        and dimensions["autonomy"]["score"] <= 35
    ):
        behaviour_state = "demonstrated_risky_behaviour"
    else:
        behaviour_state = "adequate_neutral_or_positive_evidence"

    return {
        "score": score,
        "graduated": bool(graduation_eligible and score is not None and score >= GRADUATION_THRESHOLD),
        "graduation_eligible": graduation_eligible,
        "graduation_threshold": GRADUATION_THRESHOLD,
        "assessment_state": assessment_state,
        "behaviour_state": behaviour_state,
        "breakdown": {name: value["score"] for name, value in dimensions.items()},
        "dimensions": dimensions,
        "weights": weights,
        "effective_weights": effective_weights,
        "score_version": 2,
        "is_active": trade_count > 0,
        "transactions_count": trade_count,
        "holdings_count": holdings_count,
        "confidence": confidence,
        "provisional": not enough_history,
        "evidence_sufficient": enough_history,
        "evidence_needed": {
            "trades": max(0, FULL_CONFIDENCE_TRADES - recent_trade_count),
            "holdings": max(0, FULL_CONFIDENCE_HOLDINGS - holdings_count),
            "trade_days": max(0, FULL_CONFIDENCE_TRADE_DAYS - recent_trade_days),
            "history_days": max(0, MIN_GRADUATION_HISTORY_DAYS - evidence["recent_trade_history_span_days"]),
        },
        "practice": evidence,
        "ml_behavioral_analysis": behavioral_ml.analyse_trade_anomalies(evidence),
    }


def snapshot_readiness(
    db: Session, user: User, result: dict[str, Any] | None = None
) -> ReadinessSnapshot | None:
    result = result or compute_readiness(db, user)
    if result["score"] is None:
        return None
    snap = ReadinessSnapshot(
        user_id=user.id,
        score=result["score"],
        breakdown={
            "version": 2,
            "sub": result["breakdown"],
            "weights": result["weights"],
            "effective_weights": result["effective_weights"],
            "dimensions": result["dimensions"],
            "practice": {
                "current_streak": result["practice"]["current_streak"],
                "longest_streak": result["practice"]["longest_streak"],
                "practice_days": result["practice"]["practice_days"],
            },
            "assessment_state": result["assessment_state"],
        },
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap
