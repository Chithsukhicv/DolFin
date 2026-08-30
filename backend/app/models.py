"""SQLAlchemy ORM models for DolFin.

These mirror what we'd store in Firestore once auth is wired up. Keeping
SQLite-friendly types so we can develop without external services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # "woman" | "teen"
    persona: Mapped[str] = mapped_column(String, default="woman")
    # "low" | "medium" | "high"
    risk_appetite: Mapped[str] = mapped_column(String, default="medium")
    # ISO 639-1 ("en", "hi")
    language: Mapped[str] = mapped_column(String, default="en")

    # Cash position in the simulated portfolio.
    cash: Mapped[float] = mapped_column(Float, default=100_000.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    holdings: Mapped[list["Holding"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    goals: Mapped[list["Goal"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    interventions: Mapped[list["InterventionLog"]] = relationship(back_populates="user", cascade="all,delete-orphan")


# ---------------------------------------------------------------------------
# Stock catalogue (small, hand-curated list to start)
# ---------------------------------------------------------------------------
class Stock(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "RELIANCE.NS"
    name: Mapped[str] = mapped_column(String)
    sector: Mapped[str] = mapped_column(String)
    market_cap_band: Mapped[str] = mapped_column(String)  # "large" | "mid" | "small"
    risk_level: Mapped[str] = mapped_column(String, default="medium")  # low/medium/high


# ---------------------------------------------------------------------------
# Portfolio: per-symbol holding (avg cost basis) + per-trade transaction log
# ---------------------------------------------------------------------------
class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_holding_user_symbol"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_cost: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="holdings")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)  # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    realised_pnl: Mapped[float] = mapped_column(Float, default=0.0)  # filled on sells
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Optional linkage to the active scenario / interventions firing at trade time.
    scenario_id: Mapped[str | None] = mapped_column(String, nullable=True)
    interventions_fired: Mapped[list | None] = mapped_column(JSON, nullable=True)

    user: Mapped[User] = relationship(back_populates="transactions")


# ---------------------------------------------------------------------------
# Goals (persona-aware templates)
# ---------------------------------------------------------------------------
class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    template_key: Mapped[str] = mapped_column(String)  # see services/goals.py
    label: Mapped[str] = mapped_column(String)
    target_amount: Mapped[float] = mapped_column(Float)
    horizon_months: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="goals")


# ---------------------------------------------------------------------------
# Behavioural intervention log
# ---------------------------------------------------------------------------
class InterventionLog(Base):
    __tablename__ = "intervention_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String)  # "info" | "warn" | "critical"
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    concept: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Correlates a warning with the exact preview that produced it, so a later
    # confirm/cancel resolves *these* rows and not some earlier trade's rows.
    preview_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    # Lifecycle: "pending" at preview time, then resolved to "ignored" when the
    # user trades anyway or "heeded" when they back out. Rows left "pending" mean
    # the user simply closed the modal, which is neither good nor bad behaviour.
    user_action: Mapped[str] = mapped_column(String, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="interventions")


# ---------------------------------------------------------------------------
# Market scenario (the crash / correction / rally simulator)
# ---------------------------------------------------------------------------
class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # "crash" | "correction" | "rally" | "sideways"
    severity: Mapped[float] = mapped_column(Float)  # e.g. -0.30 for a 30% crash
    duration_days: Mapped[int] = mapped_column(Integer, default=10)
    recovery_days: Mapped[int] = mapped_column(Integer, default=20)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    narrative: Mapped[str | None] = mapped_column(String, nullable=True)


# ---------------------------------------------------------------------------
# Readiness score snapshot (history kept for trend lines)
# ---------------------------------------------------------------------------
class ReadinessSnapshot(Base):
    __tablename__ = "readiness_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------------------------------------------------------------------------
# Portfolio value over time — the equity curve
# ---------------------------------------------------------------------------
class PortfolioSnapshot(Base):
    """One point on the user's portfolio-value timeline.

    This is what lets us *show* the core lesson instead of asserting it: after a
    learner holds through a simulated crash, the dip and the recovery are both
    visible on their own curve. Written on every trade and whenever a scenario
    starts or stops, so the shape of the crash is captured.
    """

    __tablename__ = "portfolio_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    total_value: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    market_value: Mapped[float] = mapped_column(Float)
    invested_cost: Mapped[float] = mapped_column(Float, default=0.0)
    unrealised_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    # What caused this point: "trade" | "scenario_start" | "scenario_stop" | "poll"
    reason: Mapped[str] = mapped_column(String, default="poll")
    scenario_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


# ---------------------------------------------------------------------------
# Quiz attempt — micro-quiz triggered after a coach explanation
# ---------------------------------------------------------------------------
class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    concept: Mapped[str] = mapped_column(String, index=True)
    score_pct: Mapped[float] = mapped_column(Float)  # 0–100
    passed: Mapped[bool] = mapped_column(Boolean)  # >= 80% counts as passed
    answers: Mapped[list] = mapped_column(JSON)  # full answer log
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------------------------------------------------------------------------
# Trade reflection — captured when a user cancels a trade after a warning
# ---------------------------------------------------------------------------
class Reflection(Base):
    __tablename__ = "reflections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)  # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Float)
    triggering_rule_ids: Mapped[list] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # user's note
    # Ties the reflection back to the specific preview the user backed out of.
    preview_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
