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
    snap = readiness_service.snapshot_readiness(db, user)
    return {
        "id": snap.id,
        "score": snap.score,
        "breakdown": snap.breakdown,
        "created_at": snap.created_at.isoformat(),
    }
