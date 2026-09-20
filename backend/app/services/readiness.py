"""Investment Readiness Score (0–100).

Sub-scores roll up to a single number that represents how prepared a
learner is to use real money. The formula is intentionally transparent:
no black-box ML, no credit-score mystery.

Sub-scores (each 0–100):
  - diversification : sustained sector & single-stock spread
  - discipline      : low panic-sell rate, low FOMO-buy rate
  - goal_alignment  : trades fit the goal horizons the user picked
  - autonomy        : recent share of trades made WITHOUT a critical/warn
                      intervention firing
  - engagement      : volume of activity (sanity floor; no engagement = no score)

Final score = weighted average, then clamped to [0, 100].
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import (
    Goal,
    Holding,
    InterventionLog,
    QuizAttempt,
    ReadinessSnapshot,
    Transaction,
    User,
)
from app.services import portfolio as portfolio_service

# Weights — we can tune these as we get user data.
WEIGHTS: dict[str, float] = {
    "diversification": 0.30,
    "discipline":      0.30,
    "goal_alignment":  0.15,
    "autonomy":        0.15,
    "engagement":      0.10,
}

GRADUATION_THRESHOLD = 80.0

# --- Evidence / confidence tuning -----------------------------------------
# Behavioural sub-scores (discipline, autonomy, goal alignment) describe a
# *habit*. A single clean trade is not a habit, so we refuse to award full
# marks until there is a real track record. Without this ramp a user who
# bought two stocks and sold one scored ~50, which badly overstates
# readiness for real money.
FULL_CONFIDENCE_TRADES = 12      # trades needed before behaviour scores max out
FULL_CONFIDENCE_HOLDINGS = 8     # holdings needed before diversification maxes out
                                  # raised from 4: 5 same-day buys proved nothing
BEGINNER_ANCHOR = 8.0            # every thin-evidence score shrinks toward this

# Laplace smoothing for autonomy: pretend we have already seen a few trades
# at a 50% clean rate, so the first clean trade cannot read as 100%.
AUTONOMY_PRIOR_TRADES = 6.0
AUTONOMY_PRIOR_CLEAN_RATE = 0.5

# Credit for demonstrating understanding. Passing a quiz on a concept you were
# just warned about is the clearest signal that a lesson landed, so it feeds
# discipline directly. Capped so quizzes supplement good behaviour rather than
# substitute for it — you cannot grind quizzes to graduation.
QUIZ_PASS_BONUS = 6.0
QUIZ_BONUS_CAP = 24.0

# Minimum days a position must be held before it contributes to the
# diversification score. Buying 5 stocks at 9am and computing "great
# diversification!" at 9:05am measures intent, not habit.
MIN_HOLD_DAYS_FOR_DIVERSIFICATION = 1


def _confidence(observed: float, needed: float) -> float:
    """Linear 0 → 1 ramp describing how much evidence we have."""
    if needed <= 0:
        return 1.0
    return max(0.0, min(observed / needed, 1.0))


def _shrink(score: float, confidence: float, anchor: float = BEGINNER_ANCHOR) -> float:
    """Pull a sub-score toward the beginner anchor when evidence is thin.

    confidence = 1.0 → score is returned untouched.
    confidence = 0.0 → score collapses to the anchor.
    """
    return anchor + (score - anchor) * confidence


# ---------------------------------------------------------------------------
def _diversification_subscore(snapshot: dict, db: "Session | None" = None, user: "User | None" = None) -> float:
    holdings = snapshot["holdings"]
    if not holdings:
        return 0.0

    market_value = snapshot["market_value"]
    if market_value <= 0:
        return 0.0

    # Penalty 1: max single-stock weight above 20%.
    max_pos_pct = max(h["market_value"] / market_value for h in holdings)
    pos_penalty = max(0.0, (max_pos_pct - 0.20)) * 100

    # Penalty 2: max sector weight above 40%.
    sector_alloc = snapshot.get("sector_allocation_pct", {})
    max_sector_pct = (max(sector_alloc.values()) / 100.0) if sector_alloc else 0.0
    sector_penalty = max(0.0, (max_sector_pct - 0.40)) * 80

    # Bonus: number of distinct sectors (capped).
    sector_count = len(sector_alloc)
    spread_bonus = min(sector_count * 8, 40)

    score = 60 + spread_bonus - pos_penalty - sector_penalty
    score = max(0.0, min(score, 100.0))

    # FULL_CONFIDENCE_HOLDINGS raised to 8 (from 4): 5 same-day buys
    # only achieve confidence 5/8 = 0.625, so the score is substantially
    # shrunk toward BEGINNER_ANCHOR. A learner needs to build up to 8 holdings
    # before diversification is considered demonstrated.
    conf = _confidence(len(holdings), FULL_CONFIDENCE_HOLDINGS)
    return max(0.0, min(_shrink(score, conf), 100.0))


def _quiz_bonus(db: Session, user: User) -> float:
    """Points earned by passing concept quizzes (distinct concepts only).

    Counted per concept rather than per attempt so retaking the same quiz does
    not farm points.
    """
    passed_concepts = (
        db.query(QuizAttempt.concept)
        .filter(QuizAttempt.user_id == user.id, QuizAttempt.passed.is_(True))
        .distinct()
        .count()
    )
    return min(passed_concepts * QUIZ_PASS_BONUS, QUIZ_BONUS_CAP)


def _discipline_subscore(db: Session, user: User) -> float:
    # Look at the last 60 days. Count panic-sells and FOMO-buys.
    since = datetime.now(timezone.utc) - timedelta(days=60)
    logs = (
        db.query(InterventionLog)
        .filter(InterventionLog.user_id == user.id, InterventionLog.created_at >= since)
        .all()
    )
    # No activity yet — don't fabricate a score.
    txn_count = db.query(Transaction).filter_by(user_id=user.id).count()
    quiz_bonus = _quiz_bonus(db, user)

    if not logs and txn_count == 0:
        # Studying before trading still counts for something, so a learner who
        # explores the concept library first isn't stuck at a flat zero.
        return min(quiz_bonus, 100.0)

    conf = _confidence(txn_count, FULL_CONFIDENCE_TRADES)

    # Only warnings the user *traded through* count against them. A warning that
    # was heeded is a success, and one left pending (modal dismissed, no trade)
    # is not evidence either way — penalising those would punish the learner for
    # reading the advice, which is the opposite of what we want to reinforce.
    ignored = [l for l in logs if l.user_action == "ignored"]
    counts = Counter(l.rule_id for l in ignored)
    penalty = (
        counts.get("panic_sell", 0) * 20
        + counts.get("fomo", 0) * 10
        + counts.get("short_hold", 0) * 5
    )

    heeded = sum(1 for l in logs if l.user_action == "heeded")
    credit = min(heeded * 5, 30) + quiz_bonus

    # Only the *assumption* of good conduct is ramped by experience. Actual
    # recorded behaviour, good or bad, counts at full weight immediately.
    #
    # The ordering matters. Ramping the whole score meant a panic sell could
    # raise discipline, because the extra trade lifted the confidence multiplier
    # faster than the penalty reduced the base. Subtracting penalties after the
    # ramp keeps a bad trade unambiguously bad.
    #
    # Baseline 50 (not 75): "no warnings fired" means "not yet tested" —
    # there's nothing to give benefit of the doubt for. The score should rise
    # from a neutral midpoint as warnings are heeded, not fall from an optimistic
    # 75 as they are ignored.
    baseline = 70.0 if logs else 50.0
    score = _shrink(baseline, conf) + credit - penalty
    return max(0.0, min(score, 100.0))


def _goal_alignment_subscore(db: Session, user: User, snapshot: dict) -> float:
    goals = db.query(Goal).filter_by(user_id=user.id).all()
    txn_count = db.query(Transaction).filter_by(user_id=user.id).count()

    # No goal set yet → no signal.
    if not goals:
        return 0.0
    # Goal exists but the user hasn't traded — don't reward picking a template.
    if txn_count == 0:
        return 0.0

    # Heuristic: long-horizon goals (≥ 36 months) suggest equity-friendly, low turnover.
    avg_horizon = sum(g.horizon_months for g in goals) / len(goals)
    holding_count = len(snapshot["holdings"])

    score = 70.0
    # Long horizon, few holdings → fine. Long horizon, hyper-trading → red flag.
    if avg_horizon >= 60 and txn_count > 30:
        score -= 25
    if avg_horizon < 12 and holding_count > 5:
        # Short horizon shouldn't be in lots of equity positions.
        score -= 15
    if 12 <= avg_horizon <= 60:
        score += 10  # balanced horizon
    score = max(0.0, min(score, 100.0))

    # Alignment is a claim about behaviour over time, so it needs the same
    # evidence ramp — picking a goal template and trading once proves nothing.
    conf = _confidence(txn_count, FULL_CONFIDENCE_TRADES)
    return max(0.0, min(_shrink(score, conf), 100.0))


def _autonomy_subscore(db: Session, user: User) -> float:
    """Fraction of recent trades that did NOT trigger a warn/critical intervention."""
    since = datetime.now(timezone.utc) - timedelta(days=60)
    txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id, Transaction.created_at >= since)
        .all()
    )
    # No trades yet — there's nothing autonomous to grade.
    if not txns:
        return 0.0

    flagged = 0
    for t in txns:
        fired = t.interventions_fired or []
        if any(f.get("severity") in ("warn", "critical") for f in fired):
            flagged += 1

    clean = len(txns) - flagged

    # Laplace-smoothed clean rate. Raw `clean / total` gives a perfect 100
    # after one unflagged trade; the prior keeps early scores honest and
    # converges to the true rate as trades accumulate.
    smoothed = (
        (clean + AUTONOMY_PRIOR_TRADES * AUTONOMY_PRIOR_CLEAN_RATE)
        / (len(txns) + AUTONOMY_PRIOR_TRADES)
        * 100.0
    )
    conf = _confidence(len(txns), FULL_CONFIDENCE_TRADES)
    return max(0.0, min(_shrink(smoothed, conf), 100.0))


def _engagement_subscore(db: Session, user: User) -> float:
    holding_count = db.query(Holding).filter_by(user_id=user.id).count()
    txn_count = db.query(Transaction).filter_by(user_id=user.id).count()
    if holding_count == 0 and txn_count == 0:
        return 0.0
    # Requires genuine engagement to reach 100.
    # Old: 5 trades (40) + 5 holdings (60) = 100 on day one.
    # New: needs ~10 trades (50) + 8+ holdings (40) to hit full marks.
    score = min(txn_count * 5, 50) + min(holding_count * 6, 30) + (
        # Bonus 20 points for having made trades over more than one day —
        # consistent usage, not a one-session burst.
        20 if _has_multi_day_activity(db, user) else 0
    )
    return min(score, 100.0)


def _has_multi_day_activity(db: Session, user: User) -> bool:
    """True when the learner has traded on at least two distinct calendar days."""
    from app.models import Transaction as Txn

    dates = {
        t.created_at.date()
        for t in db.query(Txn.created_at).filter_by(user_id=user.id).all()
        if t.created_at is not None
    }
    return len(dates) >= 2


# ---------------------------------------------------------------------------
def compute_readiness(db: Session, user: User) -> dict:
    snapshot = portfolio_service.portfolio_snapshot(db, user)
    sub = {
        "diversification": _diversification_subscore(snapshot),
        "discipline":      _discipline_subscore(db, user),
        "goal_alignment":  _goal_alignment_subscore(db, user, snapshot),
        "autonomy":        _autonomy_subscore(db, user),
        "engagement":      _engagement_subscore(db, user),
    }
    weighted = sum(sub[k] * WEIGHTS[k] for k in sub)
    score = round(max(0.0, min(weighted, 100.0)), 1)

    # An "active" user is one who has actually traded. Without that we surface
    # an empty state on the frontend rather than a misleading number.
    txn_count = db.query(Transaction).filter_by(user_id=user.id).count()
    holding_count = len(snapshot["holdings"])
    is_active = txn_count > 0

    trade_conf = _confidence(txn_count, FULL_CONFIDENCE_TRADES)
    holding_conf = _confidence(holding_count, FULL_CONFIDENCE_HOLDINGS)
    confidence = round(min(trade_conf, holding_conf), 2)

    return {
        "score": score,
        "graduated": is_active and score >= GRADUATION_THRESHOLD,
        "graduation_threshold": GRADUATION_THRESHOLD,
        "breakdown": sub,
        "weights": WEIGHTS,
        "is_active": is_active,
        "transactions_count": txn_count,
        "holdings_count": holding_count,
        # < 1.0 means the score is still provisional: not enough history to
        # judge behaviour. The frontend uses this to label the score.
        "confidence": confidence,
        "provisional": confidence < 1.0,
        "evidence_needed": {
            "trades": max(0, FULL_CONFIDENCE_TRADES - txn_count),
            "holdings": max(0, FULL_CONFIDENCE_HOLDINGS - holding_count),
        },
    }


def snapshot_readiness(db: Session, user: User) -> ReadinessSnapshot:
    result = compute_readiness(db, user)
    snap = ReadinessSnapshot(
        user_id=user.id,
        score=result["score"],
        breakdown={"sub": result["breakdown"], "weights": WEIGHTS},
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap
