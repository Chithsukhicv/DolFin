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
    from app.services import portfolio as portfolio_service

    settings = get_settings()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = portfolio_service.reset_user_portfolio(db, user, starting_cash=settings.starting_cash)
    return UserOut(**user.__dict__)
