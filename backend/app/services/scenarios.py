"""Market scenario simulator.

The simulator runs *per user* and overlays a price multiplier on top of
real Yahoo prices. This way, learners experience a believable crash
in *their* portfolio without us touching anyone else's data.

Supported scenarios:
- ``crash``      : sharp drawdown (e.g. -30%) over a few days, slow V-shape recovery
- ``correction`` : milder drawdown (-10 to -15%)
- ``rally``      : sustained upside (+20 to +30%)
- ``sideways``   : tiny noise around the base price

Multiplier curve (for crash/correction):
1. Linear drawdown across ``duration_days``  → bottom = (1 + severity)
2. Linear recovery across ``recovery_days``  → back to 1.0
3. After recovery: scenario auto-deactivates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Scenario


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def start_scenario(
    db: Session,
    user_id: str,
    kind: str,
    severity: float,
    duration_days: int = 10,
    recovery_days: int = 20,
    narrative: str | None = None,
) -> Scenario:
    """Begin a new scenario for a user. Deactivates any existing one."""
    if kind not in {"crash", "correction", "rally", "sideways"}:
        raise ValueError(f"Unknown scenario kind: {kind}")

    # Sensible bounds so a learner can't stub themselves into the floor.
    severity = max(min(severity, 0.6), -0.6)

    # Deactivate any active scenario for this user.
    for existing in db.query(Scenario).filter_by(user_id=user_id, is_active=True).all():
        existing.is_active = False

    s = Scenario(
        user_id=user_id,
        kind=kind,
        severity=severity,
        duration_days=duration_days,
        recovery_days=recovery_days,
        narrative=narrative or _default_narrative(kind, severity),
        is_active=True,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def stop_scenario(db: Session, user_id: str) -> Scenario | None:
    s = active_scenario(db, user_id)
    if not s:
        return None
    s.is_active = False
    s.ends_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(s)
    return s


def is_finished(scenario: Scenario, now: datetime | None = None) -> bool:
    """True once the drawdown and full recovery window have both elapsed."""
    now = now or datetime.now(timezone.utc)
    elapsed_days = (_seconds(now) - _seconds(scenario.started_at)) / 86_400.0
    if scenario.kind == "rally":
        # A rally plateaus and stays there; only an explicit stop ends it.
        return False
    if scenario.kind == "sideways":
        return elapsed_days > scenario.duration_days
    return elapsed_days > (scenario.duration_days + scenario.recovery_days)


def active_scenario(db: Session, user_id: str) -> Scenario | None:
    """Return the user's live scenario, lazily retiring finished ones.

    Without this, a crash that had fully recovered still reported as active:
    the multiplier returned to 1.0 but the banner kept warning about a crash and
    the presets stayed locked until the user manually pressed stop.
    """
    scenario = (
        db.query(Scenario)
        .filter(Scenario.user_id == user_id, Scenario.is_active == True)  # noqa: E712
        .order_by(Scenario.started_at.desc())
        .first()
    )
    if scenario is None:
        return None

    if is_finished(scenario):
        scenario.is_active = False
        scenario.ends_at = datetime.now(timezone.utc)
        db.commit()
        return None
    return scenario


# ---------------------------------------------------------------------------
# Multiplier curve
# ---------------------------------------------------------------------------
def _seconds(d: datetime) -> float:
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def progress_fraction(scenario: Scenario, now: datetime | None = None) -> float:
    """Return elapsed_seconds / total_scenario_seconds, clamped to [0, 1]."""
    now = now or datetime.now(timezone.utc)
    total_days = scenario.duration_days + scenario.recovery_days
    elapsed_seconds = _seconds(now) - _seconds(scenario.started_at)
    total_seconds = total_days * 86_400
    if total_seconds <= 0:
        return 1.0
    return max(0.0, min(elapsed_seconds / total_seconds, 1.0))


def current_multiplier(scenario: Scenario | None, now: datetime | None = None) -> float:
    """Compute the price multiplier for *now*.

    For ``crash`` / ``correction``:
        - phase 1 (drawdown): goes 1.0 → (1 + severity)  over duration_days
        - phase 2 (recovery): goes (1 + severity) → 1.0  over recovery_days

    For ``rally``: linear up to (1 + severity), then steady.
    For ``sideways``: ~1.0.
    """
    if scenario is None or not scenario.is_active:
        return 1.0

    now = now or datetime.now(timezone.utc)
    elapsed_days = (_seconds(now) - _seconds(scenario.started_at)) / 86_400.0

    kind = scenario.kind
    sev = scenario.severity
    dur = max(scenario.duration_days, 1)
    rec = max(scenario.recovery_days, 1)

    if kind in ("crash", "correction"):
        if elapsed_days <= 0:
            return 1.0
        if elapsed_days <= dur:
            # Linear drawdown: 1.0 → (1 + sev). sev is negative here.
            return 1.0 + sev * (elapsed_days / dur)
        if elapsed_days <= dur + rec:
            # Linear recovery from bottom back to 1.0.
            recovered = (elapsed_days - dur) / rec
            return (1.0 + sev) + (-sev) * recovered
        return 1.0  # fully recovered

    if kind == "rally":
        if elapsed_days <= 0:
            return 1.0
        if elapsed_days <= dur:
            return 1.0 + sev * (elapsed_days / dur)
        return 1.0 + sev  # rally plateaus

    # sideways: tiny deterministic wobble so charts don't look flat
    return 1.0 + (sev * 0.1)


# ---------------------------------------------------------------------------
# Apply the multiplier to a quote
# ---------------------------------------------------------------------------
def apply_to_price(price: float, scenario: Scenario | None) -> float:
    return price * current_multiplier(scenario)


def adjust_quote_dict(quote: dict, scenario: Scenario | None) -> dict:
    """Return a copy of a quote dict with scenario-adjusted price + day_change."""
    if scenario is None or not scenario.is_active:
        return {**quote, "scenario": None, "scenario_multiplier": 1.0}

    mult = current_multiplier(scenario)
    base_price = quote["price"]
    base_prev = quote.get("previous_close")

    adj_price = base_price * mult
    adj_prev = base_prev * mult if base_prev else base_prev
    day_change = (adj_price - adj_prev) if adj_prev else None
    day_change_pct = (day_change / adj_prev * 100.0) if (day_change and adj_prev) else None

    return {
        **quote,
        "price": adj_price,
        "previous_close": adj_prev,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
        "scenario": {
            "id": scenario.id,
            "kind": scenario.kind,
            "severity": scenario.severity,
            "narrative": scenario.narrative,
        },
        "scenario_multiplier": mult,
    }


def adjust_quotes(quotes: Iterable[dict], scenario: Scenario | None) -> list[dict]:
    return [adjust_quote_dict(q, scenario) for q in quotes]


def _default_narrative(kind: str, severity: float) -> str:
    if kind == "crash":
        return f"Simulated market crash: roughly {abs(severity)*100:.0f}% drawdown across the index over the coming days, followed by a slow recovery. Practise staying calm."
    if kind == "correction":
        return f"Simulated correction: about {abs(severity)*100:.0f}% pullback. Normal market behaviour — observe how your portfolio reacts."
    if kind == "rally":
        return f"Simulated rally: roughly {severity*100:.0f}% upside. Watch out for FOMO buying at the top."
    return "Simulated sideways market — small noise. Useful for boring practice."
