"""User management — stand-in until Firebase Auth is wired in."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    settings = get_settings()
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        persona=payload.persona,
        risk_appetite=payload.risk_appetite,
        language=payload.language,
        cash=settings.starting_cash,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(**user.__dict__)


@router.get("/by-email/{email}", response_model=UserOut)
def get_user_by_email(email: str, db: Session = Depends(get_db)) -> UserOut:
    """Recover an account from its email address.

    Identity lives in browser localStorage, so clearing site data previously
    orphaned the portfolio with no way back in. This is the recovery path until
    real auth is wired up; it is deliberately read-only.
    """
    user = db.query(User).filter_by(email=email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account for that email")
    return UserOut(**user.__dict__)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**user.__dict__)


@router.post("/{user_id}/reset", response_model=UserOut)
def reset_portfolio(user_id: str, db: Session = Depends(get_db)) -> UserOut:
    from app.services import indexer
    from app.services import portfolio as portfolio_service

    settings = get_settings()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = portfolio_service.reset_user_portfolio(db, user, starting_cash=settings.starting_cash)

    # The learner's retrieval corpus describes holdings and trades that no longer
    # exist. Left alone it would not be rebuilt until their next trade, and the
    # chatbot would answer confidently from deleted history.
    indexer.refresh_corpus_b_safe(db, user)
    return UserOut(**user.__dict__)


@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)) -> dict:
    """Delete a learner and everything derived from them.

    This exists because of the retrieval corpus. Corpus B is a *copy* of the
    learner's behavioural record, written for the retriever, and it is the one
    place where deleting the source rows would not be enough — orphaned chunks
    would keep describing someone who no longer exists, and with no owner row to
    match against they would sit in the table indefinitely.

    ORM cascades cover holdings, transactions, goals and intervention logs. The
    rest are listed explicitly rather than relying on cascade configuration,
    because a table added later without a cascade would silently start leaking.
    """
    from app.models import (
        AIFinding,
        ChatMessage,
        ChatSession,
        GeneratedQuestion,
        PatternAnalysis,
        PortfolioSnapshot,
        QuizAttempt,
        ReadinessSnapshot,
        Reflection,
        Scenario,
    )
    from app.services import indexer

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Chat messages hang off sessions, so they go first.
    session_ids = [
        row.id for row in db.query(ChatSession).filter_by(user_id=user_id).all()
    ]
    if session_ids:
        db.query(ChatMessage).filter(ChatMessage.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )

    removed: dict[str, int] = {}
    for model in (
        ChatSession,
        AIFinding,
        PatternAnalysis,
        GeneratedQuestion,
        Reflection,
        QuizAttempt,
        ReadinessSnapshot,
        PortfolioSnapshot,
        Scenario,
    ):
        removed[model.__tablename__] = (
            db.query(model).filter_by(user_id=user_id).delete(synchronize_session=False)
        )

    removed["knowledge_chunks"] = indexer.delete_corpus_b(db, user_id)

    db.delete(user)
    db.commit()

    return {"deleted": user_id, "removed": removed}
