"""Goal templates + per-user goals."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Goal, User
from app.schemas import GoalCreate
from app.services import goals as goals_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/templates")
def templates(persona: str | None = None):
    if persona:
        if persona not in ("woman", "teen"):
            raise HTTPException(status_code=400, detail="persona must be 'woman' or 'teen'")
        items = goals_service.for_persona(persona)
    else:
        items = goals_service.all_templates()
    return [t.__dict__ for t in items]


@router.post("")
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    template = goals_service.find(payload.template_key)
    if not template:
        raise HTTPException(status_code=404, detail="Unknown goal template")

    goal = Goal(
        user_id=user.id,
        template_key=template.key,
        label=payload.label or template.label,
        target_amount=payload.target_amount or template.suggested_amount,
        horizon_months=payload.horizon_months or template.suggested_horizon_months,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {
        "id": goal.id,
        "template_key": goal.template_key,
        "label": goal.label,
        "target_amount": goal.target_amount,
        "horizon_months": goal.horizon_months,
    }


@router.get("/user/{user_id}")
def list_user_goals(user_id: str, db: Session = Depends(get_db)):
    rows = db.query(Goal).filter_by(user_id=user_id).all()
    return [
        {
            "id": g.id,
            "template_key": g.template_key,
            "label": g.label,
            "target_amount": g.target_amount,
            "horizon_months": g.horizon_months,
        }
        for g in rows
    ]
