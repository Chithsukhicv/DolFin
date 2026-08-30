"""Concept library, glossary and the guided learning path.

These endpoints exist so a beginner can learn a concept *before* risking
anything, rather than only encountering explanations by nearly making a mistake.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.data import concepts_seed
from app.db import get_db
from app.models import User
from app.services import learning_path as path_service

router = APIRouter(prefix="/learn", tags=["learn"])


@router.get("/concepts")
def list_concepts():
    """Summaries for the library index."""
    return concepts_seed.all_concepts(summary=True)


@router.get("/glossary")
def glossary():
    """All glossary terms, for tooltips and the reference page."""
    return concepts_seed.glossary_terms()


@router.get("/concepts/{key}")
def get_concept(key: str):
    concept = concepts_seed.get_concept(key)
    if concept is None:
        raise HTTPException(status_code=404, detail="Unknown concept")
    return concept


@router.get("/path/{user_id}")
def learning_path(user_id: str, db: Session = Depends(get_db)):
    """The learner's next steps, computed from what they've actually done.

    This is what replaces dropping a new user onto an empty dashboard with no
    idea what to do next.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return path_service.build_path(db, user)
