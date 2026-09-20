"""The grounded chatbot endpoints.

Answers are assembled from retrieved material only, and the citations come back
with every reply so the frontend can show what the answer was built from. See
``services/chatbot.py`` for why that constraint exists.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import ChatAsk
from app.services import chatbot as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask")
def ask(payload: ChatAsk, db: Session = Depends(get_db)):
    """Answer one question, grounded in Corpus A, Corpus B and live market data."""
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return chat_service.ask(
        db, user, payload.question, session_id=payload.session_id
    )


@router.get("/sessions/{user_id}")
def list_sessions(user_id: str, db: Session = Depends(get_db)):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return chat_service.list_sessions(db, user_id)


@router.get("/sessions/{user_id}/{session_id}")
def transcript(user_id: str, session_id: str, db: Session = Depends(get_db)):
    """Full transcript. 404s for a session belonging to another learner."""
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    messages = chat_service.get_transcript(db, user_id, session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"session_id": session_id, "messages": messages}


@router.get("/topics")
def topics(db: Session = Depends(get_db)):
    """What the chatbot has grounded material for. Used to seed suggested prompts."""
    return {"topics": chat_service.available_topics(db, limit=8)}
