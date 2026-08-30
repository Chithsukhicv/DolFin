"""Market scenario simulator — the panic-sell training feature."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import ScenarioStart, ScenarioStop
from app.services import scenarios as scenarios_service
from app.services import valuation as valuation_service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _serialise(s) -> dict:
    if s is None:
        return None
    return {
        "id": s.id,
        "kind": s.kind,
        "severity": s.severity,
        "duration_days": s.duration_days,
        "recovery_days": s.recovery_days,
        "narrative": s.narrative,
        "is_active": s.is_active,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ends_at": s.ends_at.isoformat() if s.ends_at else None,
        "current_multiplier": scenarios_service.current_multiplier(s),
        "progress": scenarios_service.progress_fraction(s),
    }


@router.post("/start")
def start(payload: ScenarioStart, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Capture the pre-crash value first, so the equity curve has a clean
    # "before" point to fall away from.
    valuation_service.record_snapshot(db, user, reason="scenario_start")
    s = scenarios_service.start_scenario(
        db,
        user.id,
        kind=payload.kind,
        severity=payload.severity,
        duration_days=payload.duration_days,
        recovery_days=payload.recovery_days,
        narrative=payload.narrative,
    )
    return _serialise(s)


@router.post("/stop")
def stop(payload: ScenarioStop, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    s = scenarios_service.stop_scenario(db, user.id)
    if s is None:
        raise HTTPException(status_code=404, detail="No active scenario")
    valuation_service.record_snapshot(db, user, reason="scenario_stop", scenario_id=s.id)
    return _serialise(s)


@router.get("/active/{user_id}")
def active(user_id: str, db: Session = Depends(get_db)):
    s = scenarios_service.active_scenario(db, user_id)
    return _serialise(s)


@router.get("/presets")
def presets():
    """Quick presets the UI can offer to users without thinking about numbers."""
    return [
        {"kind": "correction", "severity": -0.10, "duration_days": 5,  "recovery_days": 10,
         "label": "Mild correction (-10%)"},
        {"kind": "crash",      "severity": -0.30, "duration_days": 10, "recovery_days": 20,
         "label": "Sharp crash (-30%)"},
        {"kind": "crash",      "severity": -0.50, "duration_days": 14, "recovery_days": 45,
         "label": "Major bear market (-50%)"},
        {"kind": "rally",      "severity":  0.25, "duration_days": 14, "recovery_days":  1,
         "label": "Bull rally (+25%)"},
        {"kind": "sideways",   "severity":  0.02, "duration_days": 30, "recovery_days":  1,
         "label": "Boring sideways"},
    ]
