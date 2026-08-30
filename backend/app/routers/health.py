"""Health-check endpoints."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict:
    return {"name": "DolFin API", "version": "0.1.0", "status": "ok"}


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.app_env,
    }
