"""Market Insights Service.

Combines the ML forecast, the user's behavioural pattern analysis, recent
deterministic intervention warnings, and RAG-retrieved financial education
material into a single structured package.  That package is passed to the
LLM gateway as a list of PromptSection objects so the AI can narrate factual
context rather than invent predictions.

Key design constraints
----------------------
* Probabilities are passed as labelled facts ("1-day model: UP 52%"), never
  as instructions to predict.
* Forecast is omitted from the prompt when model_status is 'not_trained' or
  'insufficient_history' for ALL horizons.
* This function NEVER writes to InterventionLog — all persisted output goes
  to AIFinding (kind='market_prediction').  Writing to InterventionLog would
  corrupt the Investment Readiness Score.
* The function never raises; it always returns a dict with 'mode' set to
  'offline' on failure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AIFinding, InterventionLog, User
from app.services import llm_gateway, pattern_analyzer, retrieval
from app.services.llm_gateway import PromptSection
from app.services.market_ml import get_forecast

log = logging.getLogger(__name__)

# Statuses that carry usable probabilities.
_LIVE_STATUSES = frozenset({"ok", "stale"})


def _format_forecast_section(forecast) -> str | None:
    """Render forecast probabilities as labelled factual context for the prompt.

    Returns None when no horizon has a live prediction.
    """
    lines: list[str] = []
    for hf in forecast.horizons:
        if hf.model_status not in _LIVE_STATUSES:
            lines.append(
                f"{hf.horizon_days}-day: model not available ({hf.model_status})"
            )
            continue
        unc = " [low confidence]" if hf.uncertainty_flag else ""
        stale = " [stale model]" if hf.is_stale else ""
        lines.append(
            f"{hf.horizon_days}-day: "
            f"UP {hf.prob_up:.0%}, SIDEWAYS {hf.prob_sideways:.0%}, DOWN {hf.prob_down:.0%}"
            f"  →  {hf.predicted_class}{unc}{stale}"
        )

    if all(hf.model_status not in _LIVE_STATUSES for hf in forecast.horizons):
        return None

    header = (
        f"Market direction model output for {forecast.symbol} "
        f"(experimental — not financial advice):"
    )
    return header + "\n" + "\n".join(lines)


def _recent_intervention_lines(db: Session, user: User) -> str:
    """Return a brief text summary of warnings logged in the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(InterventionLog)
        .filter(
            InterventionLog.user_id == user.id,
            InterventionLog.created_at >= cutoff,
        )
        .order_by(InterventionLog.created_at.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return "No intervention warnings in the last 30 days."
    return "\n".join(
        f"- [{r.severity.upper()}] {r.title} ({r.user_action})" for r in rows
    )


def get_market_insight(
    db: Session,
    user: User,
    symbol: str,
) -> dict[str, Any]:
    """Assemble forecast + patterns + intervention context + RAG, call LLM.

    Parameters
    ----------
    db:     SQLAlchemy session.
    user:   The requesting User ORM object.
    symbol: Ticker symbol (will be normalised by get_forecast).

    Returns
    -------
    dict with keys:
        forecast    — MarketForecastResponse
        patterns    — result of pattern_analyzer.analyse()
        llm_result  — GatewayResult
        citations   — list of citation dicts from retrieval
        mode        — 'generated' | 'cached' | 'offline'
    """
    try:
        return _get_market_insight(db, user, symbol)
    except Exception as exc:  # pragma: no cover
        log.error("get_market_insight failed for symbol=%r user=%s: %s", symbol, user.id, exc)
        return {
            "forecast": None,
            "patterns": None,
            "llm_result": None,
            "citations": [],
            "mode": "offline",
        }


def _get_market_insight(db: Session, user: User, symbol: str) -> dict[str, Any]:
    # ── 1. Forecast ──────────────────────────────────────────────────────────
    forecast = get_forecast(symbol)

    # ── 2. Behavioural patterns ───────────────────────────────────────────────
    patterns = pattern_analyzer.analyse(db, user)

    # ── 3. Recent deterministic warnings (read-only from InterventionLog) ─────
    intervention_text = _recent_intervention_lines(db, user)

    # ── 4. RAG retrieval ──────────────────────────────────────────────────────
    # Build a query from the symbol and the dominant predicted direction.
    live_forecasts = [hf for hf in forecast.horizons if hf.model_status in _LIVE_STATUSES]
    dominant_class = (
        max(live_forecasts, key=lambda hf: hf.prob_up or 0.0).predicted_class
        if live_forecasts
        else None
    )
    query = f"{symbol} market direction {dominant_class or 'volatility'} investing risk"
    retrieved = retrieval.retrieve(
        db,
        query,
        user_id=user.id,
        corpus="both",
        top_k=5,
    )

    # ── 5. Assemble PromptSection list ────────────────────────────────────────
    sections: list[PromptSection] = [
        PromptSection(
            "Who this is",
            f"A {user.persona} learner with {user.risk_appetite} risk appetite "
            f"(language: {user.language}).",
        ),
    ]

    forecast_text = _format_forecast_section(forecast)
    if forecast_text:
        sections.append(
            PromptSection(
                f"Model forecast for {forecast.symbol}",
                forecast_text + (
                    "\n\nThese are output probabilities from an experimental classifier. "
                    "They represent model estimates, not guaranteed outcomes. "
                    "Do not present them as price predictions."
                ),
            )
        )

    if patterns.get("status") not in ("insufficient_activity",):
        pattern_lines = "\n".join(
            f"- {p['label']}: {p['evidence']}"
            for p in patterns.get("patterns", [])
        )
        if pattern_lines:
            sections.append(
                PromptSection("Behavioural patterns", pattern_lines)
            )

    sections.append(
        PromptSection("Recent rule-engine warnings (last 30 days)", intervention_text)
    )

    if retrieved.chunks:
        sections.append(
            PromptSection("Reference material from the knowledge base", retrieved.as_evidence())
        )

    sections.append(
        PromptSection(
            "Task",
            "In 2–3 short paragraphs, help the learner understand what these market "
            "signals and their own behavioural patterns suggest about the current "
            "situation. Explain uncertainty clearly. Never tell them to buy or sell. "
            "Never present model probabilities as certainties. Reference specific "
            "numbers from the forecast section as context, not predictions.",
        )
    )

    # ── 6. LLM call ───────────────────────────────────────────────────────────
    llm_result = llm_gateway.generate(
        "market_insight",
        sections,
        language=user.language,
        user_id=user.id,
    )

    # Deterministic fallback if LLM unavailable
    if llm_result.unavailable:
        body = _deterministic_summary(forecast, patterns)
    else:
        body = llm_result.text

    # ── 7. Persist to AIFinding (never InterventionLog) ───────────────────────
    finding = AIFinding(
        user_id=user.id,
        kind="market_prediction",
        severity="info",
        title=f"Market outlook: {forecast.symbol}",
        body=body,
        concept=None,
        preview_id=None,
        citations=retrieved.citations(),
    )
    db.add(finding)
    db.commit()

    return {
        "forecast": forecast,
        "patterns": patterns,
        "llm_result": llm_result,
        "citations": retrieved.citations(),
        "mode": llm_result.mode if not llm_result.unavailable else "offline",
    }


def _deterministic_summary(forecast, patterns: dict) -> str:
    """Minimal text summary produced without the LLM."""
    live = [hf for hf in forecast.horizons if hf.model_status in _LIVE_STATUSES]
    if not live:
        model_note = "No trained model is available for this symbol yet."
    else:
        parts = [
            f"{hf.horizon_days}-day {hf.predicted_class} "
            f"(UP {hf.prob_up:.0%} / SIDEWAYS {hf.prob_sideways:.0%} / DOWN {hf.prob_down:.0%})"
            for hf in live
        ]
        model_note = "Experimental model output (not financial advice): " + "; ".join(parts) + "."

    pattern_note = ""
    if patterns.get("patterns"):
        labels = [p["label"] for p in patterns["patterns"][:2]]
        pattern_note = " Behavioural patterns noted: " + ", ".join(labels) + "."

    return (
        model_note
        + pattern_note
        + " This is an experimental educational feature. "
        + "Past model output does not guarantee future results."
    )
