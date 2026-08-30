"""Quiz endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import QuizAttempt, User
from app.schemas import QuizSubmit
from app.services import quizzes as quizzes_service

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("/{concept}")
def get_quiz(concept: str):
    items = quizzes_service.get_quiz(concept)
    if not items:
        raise HTTPException(status_code=404, detail="No quiz for this concept")
    return {"concept": concept, "questions": items}


@router.post("/submit")
def submit(payload: QuizSubmit, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not quizzes_service.get_quiz(payload.concept):
        raise HTTPException(status_code=404, detail="No quiz for this concept")
    attempt = quizzes_service.record_attempt(db, user, payload.concept, payload.answers)
    return {
        "id": attempt.id,
        "concept": attempt.concept,
        "score_pct": attempt.score_pct,
        "passed": attempt.passed,
        "answers": attempt.answers,
        "created_at": attempt.created_at.isoformat(),
    }


@router.get("/user/{user_id}")
def list_attempts(user_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(QuizAttempt)
        .filter_by(user_id=user_id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "concept": r.concept,
            "score_pct": r.score_pct,
            "passed": r.passed,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
