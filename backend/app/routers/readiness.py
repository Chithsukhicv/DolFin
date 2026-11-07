"""Readiness Score endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import readiness as readiness_service

router = APIRouter(prefix="/readiness", tags=["readiness"])


@router.get("/{user_id}")
def get_readiness(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return readiness_service.compute_readiness(db, user)


@router.post("/{user_id}/snapshot")
def snapshot(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    result = readiness_service.compute_readiness(db, user)
    snap = readiness_service.snapshot_readiness(db, user, result)
    if snap is None:
        return {
            "id": None,
            "score": None,
            "breakdown": {
                "version": 2,
                "sub": result["breakdown"],
                "weights": result["weights"],
                "effective_weights": result["effective_weights"],
                "dimensions": result["dimensions"],
            },
            "assessment_state": result["assessment_state"],
            "snapshot_recorded": False,
            "created_at": None,
        }
    return {
        "id": snap.id,
        "score": snap.score,
        "breakdown": snap.breakdown,
        "assessment_state": "assessable",
        "snapshot_recorded": True,
        "created_at": snap.created_at.isoformat(),
    }
