"""Quiz scoring service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.data.quizzes_seed import quizzes_for_concept
from app.models import QuizAttempt, User

PASS_THRESHOLD_PCT = 80.0


def get_quiz(concept: str) -> list[dict]:
    """Return quiz questions for a concept *without* the answer field."""
    raw = quizzes_for_concept(concept)
    return [
        {"index": i, "question": q["question"], "options": q["options"]}
        for i, q in enumerate(raw)
    ]


def score_attempt(concept: str, user_answers: list[int]) -> dict:
    raw = quizzes_for_concept(concept)
    if not raw:
        return {
            "concept": concept,
            "score_pct": 0.0,
            "passed": False,
            "total": 0,
            "correct": 0,
            "answers": [],
        }
    correct = 0
    detail = []
    for i, q in enumerate(raw):
        given = user_answers[i] if i < len(user_answers) else -1
        is_correct = given == q["answer"]
        if is_correct:
            correct += 1
        detail.append({
            "index": i,
            "question": q["question"],
            "options": q["options"],
            "given": given,
            "correct_answer": q["answer"],
            "is_correct": is_correct,
            # The teaching payload. Returned for correct answers too, so a lucky
            # guess still leaves the learner with the reasoning.
            "explanation": q.get("explanation", ""),
        })
    pct = (correct / len(raw)) * 100.0
    return {
        "concept": concept,
        "score_pct": round(pct, 1),
        "passed": pct >= PASS_THRESHOLD_PCT,
        "total": len(raw),
        "correct": correct,
        "answers": detail,
    }


def record_attempt(db: Session, user: User, concept: str, user_answers: list[int]) -> QuizAttempt:
    result = score_attempt(concept, user_answers)
    attempt = QuizAttempt(
        user_id=user.id,
        concept=concept,
        score_pct=result["score_pct"],
        passed=result["passed"],
        answers=result["answers"],
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt
