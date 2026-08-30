"""DolFin FastAPI entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import SessionLocal, init_models
from app.routers import (
    catalog,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and seed the stock catalogue on cold start.
    init_models()
    from app.data.stocks_seed import seed_if_empty

    with SessionLocal() as db:
        seed_if_empty(db)
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

    return app


app = create_app()
