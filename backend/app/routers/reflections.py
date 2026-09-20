"""Reflection endpoints — capture *why* a user heeded a warning."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import logging

from app.db import get_db
from app.models import Reflection, User
from app.schemas import ReflectionCreate
from app.services import indexer
from app.services import interventions as interventions_service
from app.services import reflection_analyzer

log = logging.getLogger(__name__)

router = APIRouter(prefix="/reflections", tags=["reflections"])


@router.post("")
def create(payload: ReflectionCreate, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Store the learner's text first. R4.11 requires a stored reason and a
    # returned acknowledgement to always occur together, so if this write fails
    # the request fails rather than returning an acknowledgement for lost text.
    ref = Reflection(
        user_id=user.id,
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity,
        triggering_rule_ids=payload.triggering_rule_ids,
        reason=payload.reason,
        preview_id=payload.preview_id,
    )
    db.add(ref)
    db.commit()

    # Credit the warnings from *this* preview as heeded. Matching on preview_id
    # instead of rule_id matters: the old rule_id lookup could retroactively
    # rewrite logs from earlier, already-executed trades.
    heeded_count = interventions_service.resolve_preview(
        db, user, payload.preview_id or "", "heeded"
    )

    # Assess the learner's written reasoning. Advisory only — the heeded count
    # above is already final regardless of what the analysis concludes.
    analysis = reflection_analyzer.analyse(
        db, user, ref, rule_ids=payload.triggering_rule_ids
    )

    # The learner's record changed, so their retrieval corpus is now stale.
    indexer.refresh_corpus_b_safe(db, user)

    db.refresh(ref)
    return {
        "id": ref.id,
        "symbol": ref.symbol,
        "side": ref.side,
        "quantity": ref.quantity,
        "triggering_rule_ids": ref.triggering_rule_ids,
        "reason": ref.reason,
        "preview_id": ref.preview_id,
        "warnings_heeded": heeded_count,
        "analysis": analysis,
        "created_at": ref.created_at.isoformat(),
    }


@router.get("/user/{user_id}")
def list_reflections(user_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Reflection)
        .filter_by(user_id=user_id)
        .order_by(Reflection.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "side": r.side,
            "quantity": r.quantity,
            "triggering_rule_ids": r.triggering_rule_ids,
            "reason": r.reason,
            "preview_id": r.preview_id,
            # The AI's read on the learner's reasoning, so a past reflection can
            # be revisited with its assessment intact. Omitting these meant the
            # most valuable teaching moment in the app existed for one screen and
            # then vanished.
            "reasoning_class": r.reasoning_class,
            "ai_response": r.ai_response,
            "ai_citations": r.ai_citations or [],
            "ai_mode": r.ai_mode,
            "source": "ai" if r.ai_response else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
