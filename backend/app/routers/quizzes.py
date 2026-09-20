"""Quiz endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import QuizAttempt, User
from app.schemas import AdaptiveQuizSubmit, QuizSubmit
from app.services import indexer, quiz_generator
from app.services import quizzes as quizzes_service

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


# ---------------------------------------------------------------------------
# Adaptive quizzes
# ---------------------------------------------------------------------------
# Declared before "/{concept}" so the literal paths win the route match. FastAPI
# resolves in declaration order, and "/adaptive" would otherwise be swallowed as
# a concept name.
@router.get("/adaptive/{user_id}/{concept}")
def adaptive_quiz(user_id: str, concept: str, db: Session = Depends(get_db)):
    """Fresh questions on a concept, generated from its own Corpus A material.

    Falls back to seeded questions per unfilled slot, so the learner always gets
    a full quiz. 422 only when neither source can supply a single question.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    quiz = quiz_generator.build_quiz(db, user, concept)
    if quiz["status"] != "ok":
        raise HTTPException(
            status_code=422,
            detail=f"No question available for the concept '{concept}'.",
        )
    return quiz


@router.get("/adaptive/{user_id}")
def adaptive_targets(user_id: str, db: Session = Depends(get_db)):
    """Concepts worth re-testing — the ones this learner attempted and failed."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"concepts": quiz_generator.failed_concepts(db, user)}


@router.post("/adaptive/submit")
def submit_adaptive(payload: AdaptiveQuizSubmit, db: Session = Depends(get_db)):
    """Score a generated quiz against the stored answers."""
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    attempt = quiz_generator.record(
        db, user, payload.concept, payload.question_ids, payload.answers
    )
    if attempt is None:
        raise HTTPException(
            status_code=400,
            detail="Those questions do not belong to this learner and concept.",
        )
    indexer.refresh_corpus_b_safe(db, user)
    return {
        "id": attempt.id,
        "concept": attempt.concept,
        "score_pct": attempt.score_pct,
        "passed": attempt.passed,
        "answers": attempt.answers,
        "created_at": attempt.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Seeded quizzes
# ---------------------------------------------------------------------------
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
    # Corpus B carries a summary of which concepts the learner has passed, so the
    # chatbot can answer "what have I actually understood?" accurately.
    indexer.refresh_corpus_b_safe(db, user)
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
