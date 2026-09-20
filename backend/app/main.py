"""DolFin FastAPI entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import SessionLocal, init_models
from app.routers import (
    catalog,
    chat,
    coach,
    goals,
    health,
    history,
    learn,
    market,
    portfolio,
    quizzes,
    readiness,
    reflections,
    scenarios,
    users,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and seed the stock catalogue on cold start.
    init_models()
    from app.data.stocks_seed import sync_catalogue
    from app.services import indexer

    with SessionLocal() as db:
        # Reconcile rather than insert-only: retired tickers have to leave the
        # catalogue, or they stay browsable and fail at trade time.
        cat = sync_catalogue(db)
        if cat["inserted"] or cat["updated"] or cat["removed"]:
            log.info(
                "Catalogue synced: %d symbols (+%d new, %d updated, %d retired)",
                cat["total"], cat["inserted"], cat["updated"], cat["removed"],
            )

        # Corpus A is derived deterministically from the concept library, the
        # glossary, quiz explanations and the rule definitions, so re-indexing on
        # boot keeps it in step with the code without a deploy step to remember.
        # Idempotent via stable chunk keys, and embeddings are skipped here so a
        # cold start never blocks on a network call — the lexical ranker works
        # immediately and vectors get attached by the reindex script.
        try:
            result = indexer.reindex_corpus_a(db, embed=False)
            log.info(
                "Corpus A ready: %d chunks (+%d new, %d updated, %d removed)",
                result["total"], result["inserted"], result["updated"], result["deleted"],
            )
        except Exception as e:
            # A retrieval index that failed to build must not stop the app; every
            # AI feature degrades to its deterministic fallback.
            log.warning("Corpus A indexing failed on startup: %s", e)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DolFin API",
        version="0.1.0",
        description="Gamified investment learning platform — backend.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(market.router)
    app.include_router(users.router)
    app.include_router(catalog.router)
    app.include_router(portfolio.router)
    app.include_router(goals.router)
    app.include_router(scenarios.router)
    app.include_router(readiness.router)
    app.include_router(quizzes.router)
    app.include_router(reflections.router)
    app.include_router(history.router)
    app.include_router(learn.router)
    app.include_router(coach.router)
    app.include_router(chat.router)

    return app


app = create_app()
