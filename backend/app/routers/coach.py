"""Whole-history behavioural analysis.

Separate from the trade-time coach message in ``services/coach.py``: that one
explains a single warning, this one reads across the learner's entire record and
names the habit. Output is advisory and flagged ``source="ai"`` — it lives in
``ai_findings``, never in ``intervention_logs``, so it cannot reach the Readiness
Score.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import pattern_analyzer

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/patterns/{user_id}")
def patterns(
    user_id: str,
    force: bool = Query(
        False, description="Bypass the cache and recompute. Costs a model call."
    ),
    db: Session = Depends(get_db),
):
    """Named patterns in this learner's behaviour, with the counts behind them."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return pattern_analyzer.analyse(db, user, force=force)


@router.get("/evidence/{user_id}")
def evidence(user_id: str, db: Session = Depends(get_db)):
    """The counted facts on their own, with no model involvement.

    Useful for showing a learner exactly what the analysis was computed from —
    and for verifying that every number in a generated pattern came from here.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return pattern_analyzer.build_evidence(db, user)
