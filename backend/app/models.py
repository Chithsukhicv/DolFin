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
# RAG: retrievable knowledge chunks
# ---------------------------------------------------------------------------
class KnowledgeChunk(Base):
    """One retrievable unit of text, from either corpus.

    Two corpora share this table because retrieval ranks across both in a single
    pass, and keeping them together means there is exactly one code path — and
    therefore exactly one place where per-user access control is enforced.

    ``corpus='A'`` is curated content shared by everyone (``owner_user_id`` null).
    ``corpus='B'`` is one learner's own behavioural record, and is the reason the
    owner column exists: a leak here would expose one learner's trades to another.

    ``chunk_key`` is a stable, human-derived identity (e.g.
    ``concept:panic_selling:section:2``) so re-indexing updates rows in place
    rather than duplicating them.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("chunk_key", name="uq_chunk_key"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    corpus: Mapped[str] = mapped_column(String, index=True)  # "A" | "B"
    chunk_key: Mapped[str] = mapped_column(String, index=True)
    # Null for Corpus A. Set for every Corpus B chunk.
    owner_user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    source_title: Mapped[str] = mapped_column(String)
    source_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(String)

    # Stored as JSON so the schema stays portable to Firestore, which has no
    # native float-array column. Null when no embedding provider is configured;
    # the retriever falls back to lexical ranking in that case.
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)

    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


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

    # AI assessment of the learner's written reasoning. Rules cannot read free
    # text at all, so this is entirely AI-provided. The classification is
    # advisory: it never changes whether the warning counted as heeded, because
    # backing out is good behaviour regardless of how well the learner justified it.
    reasoning_class: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_response: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_mode: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------------------------------------------------------------------------
# AI reasoning layer output — advisory, never scored
# ---------------------------------------------------------------------------
class AIFinding(Base):
    """An advisory observation produced by the AI layer.

    Kept in its own table, deliberately NOT in ``intervention_logs``. That
    separation is the enforcement mechanism for the determinism boundary: the
    Readiness Score reads only ``intervention_logs``, so no AI output can reach
    scoring even by accident. ``source`` is stored anyway so the distinction
    survives being serialised into an API response.
    """

    __tablename__ = "ai_findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # Correlates with the trade preview that triggered the review, when there was one.
    preview_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    kind: Mapped[str] = mapped_column(String, index=True)  # "risk_review" | "pattern" | ...
    severity: Mapped[str] = mapped_column(String, default="info")  # display ordering only
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    concept: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String, default="ai")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class PatternAnalysis(Base):
    """A cached whole-history behavioural analysis.

    Regenerating this on every page load would be slow and wasteful, so the
    record counts it was computed from are stored alongside it. If none of those
    counts have changed, the cached analysis is still valid and no model call is
    made.
    """

    __tablename__ = "pattern_analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    patterns: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String, default="offline")

    # Cache-validity fingerprint.
    txn_count: Mapped[int] = mapped_column(Integer, default=0)
    resolved_intervention_count: Mapped[int] = mapped_column(Integer, default=0)
    quiz_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    reflection_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class ChatSession(Base):
    """A conversation with the grounded chatbot."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all,delete-orphan"
    )


class ChatMessage(Base):
    """One turn. Citations are stored so an answer stays auditable later."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class GeneratedQuestion(Base):
    """An AI-generated quiz question, kept so attempts stay reproducible."""

    __tablename__ = "generated_questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    concept: Mapped[str] = mapped_column(String, index=True)
    question: Mapped[str] = mapped_column(String)
    options: Mapped[list] = mapped_column(JSON)
    answer: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(String)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
