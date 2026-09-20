"""Health-check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict:
    return {"name": "DolFin API", "version": "0.1.0", "status": "ok"}


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    # LLM counters and corpus sizes are surfaced here so quota, cache and
    # retrieval behaviour are observable in a deployed environment without adding
    # a separate metrics endpoint. A zero corpus_a count is the single clearest
    # signal that the RAG layer is not actually grounded.
    from app.services import indexer, llm_gateway

    try:
        corpora = indexer.corpus_stats(db)
    except Exception as e:  # a health check must not 500
        corpora = {"error": str(e)}

    return {
        "status": "ok",
        "env": settings.app_env,
        "llm": llm_gateway.stats(),
        "corpora": corpora,
    }
