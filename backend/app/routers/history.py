"""Read-only history endpoints for transactions, interventions, snapshots."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import InterventionLog, QuizAttempt, ReadinessSnapshot, Transaction, User
from app.services import valuation as valuation_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/transactions/{user_id}")
def transactions(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    rows = (
        db.query(Transaction)
        .filter_by(user_id=user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "fee": t.fee,
            "realised_pnl": t.realised_pnl,
            "scenario_id": t.scenario_id,
            "interventions_fired": t.interventions_fired or [],
            "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]


@router.get("/interventions/{user_id}")
def interventions(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    rows = (
        db.query(InterventionLog)
        .filter_by(user_id=user_id)
        .order_by(InterventionLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "rule_id": r.rule_id,
            "severity": r.severity,
            "title": r.title,
            "message": r.message,
            "concept": r.concept,
            "user_action": r.user_action,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/equity/{user_id}")
def equity_curve(
    user_id: str,
    limit: int = Query(500, ge=2, le=2000),
    db: Session = Depends(get_db),
):
    """Portfolio value over time — the chart that shows a crash and its recovery."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Refresh the tail so the curve reflects current prices when the page loads.
    valuation_service.record_poll(db, user)
    return valuation_service.equity_curve(db, user, limit=limit)


@router.get("/interventions/{user_id}/summary")
def intervention_summary(user_id: str, db: Session = Depends(get_db)):
    """Counts of how the learner responded to warnings, grouped by concept.

    Powers the coach page's progress view: which concepts keep tripping them up,
    and which they have started to act on.
    """
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    rows = db.query(InterventionLog).filter_by(user_id=user_id).all()

    by_concept: dict[str, dict] = {}
    for r in rows:
        key = r.concept or "other"
        entry = by_concept.setdefault(
            key, {"concept": key, "fired": 0, "heeded": 0, "ignored": 0, "pending": 0}
        )
        entry["fired"] += 1
        action = r.user_action or "pending"
        if action in entry:
            entry[action] += 1

    passed = {
        c for (c,) in db.query(QuizAttempt.concept)
        .filter(QuizAttempt.user_id == user_id, QuizAttempt.passed.is_(True))
        .distinct()
        .all()
    }
    for key, entry in by_concept.items():
        entry["quiz_passed"] = key in passed
        resolved = entry["heeded"] + entry["ignored"]
        entry["heed_rate"] = round(entry["heeded"] / resolved * 100, 1) if resolved else None

    return sorted(by_concept.values(), key=lambda e: -e["fired"])


@router.get("/readiness/{user_id}")
def readiness_history(
    user_id: str,
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    rows = (
        db.query(ReadinessSnapshot)
        .filter_by(user_id=user_id)
        .order_by(ReadinessSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "score": s.score,
            "breakdown": s.breakdown,
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]
