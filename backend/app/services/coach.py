"""Context-aware coaching.

The rule engine decides *what* fired. This module decides *how it is said* — and
that is a genuinely different job. The same `concentration` warning should read
differently for a learner on their third trade who has already panic-sold twice
than for one with forty trades who has heeded nine of their last ten warnings.
Rules cannot make that distinction; it needs the learner's history as context.

Every call goes through ``llm_gateway``, so safety constraints, injection
handling, timeouts, caching and budgeting are inherited rather than
reimplemented. When the gateway reports unavailable, a deterministic message is
returned and ``mode`` says ``offline`` — the platform stays fully usable with no
API key.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Goal, InterventionLog, Transaction, User
from app.services import llm_gateway
from app.services.llm_gateway import PromptSection

log = logging.getLogger(__name__)

_PERSONA_TONE = {
    "woman": "Warm and supportive. Treat the user as an intelligent peer building independence.",
    "teen": "Friendly, encouraging, plain language, no jargon. Never preachy.",
}


# ---------------------------------------------------------------------------
# Learner context — the input rules cannot use
# ---------------------------------------------------------------------------
def build_learner_context(db: Session, user: User, rule_ids: list[str]) -> dict:
    """Summarise the learner's track record for the prompt.

    Deliberately returns counted facts rather than prose. The model is good at
    phrasing and bad at arithmetic, so every number here is computed in Python
    and handed over as ground truth.
    """
    txn_count = db.query(Transaction).filter_by(user_id=user.id).count()

    logs = db.query(InterventionLog).filter_by(user_id=user.id).all()
    resolved = [l for l in logs if l.user_action in ("heeded", "ignored")]
    heeded = sum(1 for l in resolved if l.user_action == "heeded")
    heed_rate = round(heeded / len(resolved), 2) if resolved else None

    # How often has this learner traded through *these specific* warnings before?
    repeats = {
        rid: sum(1 for l in logs if l.rule_id == rid and l.user_action == "ignored")
        for rid in rule_ids
    }

    # Heed rate for the concepts attached to the rules that just fired.
    concepts = {l.concept for l in logs if l.rule_id in rule_ids and l.concept}
    concept_rates: dict[str, float] = {}
    for concept in concepts:
        rows = [l for l in resolved if l.concept == concept]
        if rows:
            hits = sum(1 for l in rows if l.user_action == "heeded")
            concept_rates[concept] = round(hits / len(rows), 2)

    goals = db.query(Goal).filter_by(user_id=user.id).all()
    horizon = (
        int(sum(g.horizon_months for g in goals) / len(goals)) if goals else None
    )

    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent_trades = sum(
        1 for t in db.query(Transaction).filter_by(user_id=user.id).all()
        if (t.created_at.replace(tzinfo=timezone.utc) if t.created_at.tzinfo is None
            else t.created_at) >= since
    )

    return {
        "trades_total": txn_count,
        "trades_last_30_days": recent_trades,
        "warnings_resolved": len(resolved),
        "heed_rate_overall": heed_rate,
        "heed_rate_by_concept": concept_rates,
        "times_ignored_these_rules": {k: v for k, v in repeats.items() if v},
        "goal_horizon_months": horizon,
        "risk_appetite": user.risk_appetite,
        "persona": user.persona,
    }


def _context_lines(ctx: dict) -> str:
    """Render the context dict as compact prompt lines."""
    lines = [
        f"- Trades placed so far: {ctx['trades_total']} ({ctx['trades_last_30_days']} in the last 30 days)",
        f"- Risk appetite: {ctx['risk_appetite']}",
    ]
    if ctx["goal_horizon_months"]:
        lines.append(f"- Goal horizon: about {ctx['goal_horizon_months']} months")
    if ctx["heed_rate_overall"] is not None:
        lines.append(
            f"- Heeds {int(ctx['heed_rate_overall'] * 100)}% of warnings "
            f"({ctx['warnings_resolved']} resolved so far)"
        )
    else:
        lines.append("- No warnings resolved yet; this may be their first")
    for concept, rate in ctx["heed_rate_by_concept"].items():
        lines.append(f"- Heed rate on {concept.replace('_', ' ')}: {int(rate * 100)}%")
    for rule_id, count in ctx["times_ignored_these_rules"].items():
        lines.append(f"- Has traded through the {rule_id} warning {count} time(s) before")
    return "\n".join(lines)


def _tone_guidance(ctx: dict) -> str:
    """Pick the register from the learner's actual record.

    This is the whole point of the feature: a repeat offender and someone with a
    strong track record should not receive the same words.
    """
    repeats = sum(ctx["times_ignored_these_rules"].values())
    heed = ctx["heed_rate_overall"]

    if repeats >= 2:
        return (
            "This learner has traded through this same warning more than once. "
            "Name the repetition directly but without shaming, and make the cost "
            "of the pattern concrete."
        )
    if heed is not None and heed >= 0.80:
        return (
            "This learner heeds most warnings. Acknowledge that track record first, "
            "then restate the concern briefly — they have earned the benefit of the doubt."
        )
    if ctx["trades_total"] <= 2:
        return (
            "This is one of the learner's first trades. Frame the warning as "
            "orientation rather than correction, and keep it encouraging."
        )
    return "Be direct and practical. State the concern and the next step."


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def coach_explain(
    interventions: Iterable[dict],
    *,
    persona: str = "woman",
    language: str = "en",
    side: str | None = None,
    symbol: str | None = None,
    quantity: float | None = None,
    db: Session | None = None,
    user: User | None = None,
) -> dict:
    """Turn fired rules into one friendly, context-aware message.

    ``db`` and ``user`` are optional so existing callers keep working; when both
    are supplied the message becomes history-aware rather than generic.
    """
    items = list(interventions)
    if not items:
        return {
            "mode": "none",
            "message": _clean_trade_message(side, symbol, quantity, language),
        }

    rule_ids = [i["rule_id"] for i in items]
    ctx = (
        build_learner_context(db, user, rule_ids)
        if (db is not None and user is not None)
        else None
    )

    sections = [
        PromptSection("Tone", _PERSONA_TONE.get(persona, _PERSONA_TONE["woman"])),
    ]
    if side and symbol and quantity:
        sections.append(
            PromptSection("Proposed trade", f"{side} {quantity:g} units of {symbol}")
        )
    sections.append(
        PromptSection(
            "Warnings the rule engine raised",
            "\n".join(
                f"- [{i['severity'].upper()}] {i['title']}: {i['message']}"
                for i in items
            ),
        )
    )
    if ctx:
        sections.append(PromptSection("This learner's track record", _context_lines(ctx)))
        sections.append(PromptSection("How to pitch it", _tone_guidance(ctx)))

    sections.append(
        PromptSection(
            "Task",
            "Write ONE message under 120 words that acknowledges what they are about "
            "to do, explains the most serious concern in plain language, teaches the "
            "underlying idea in a line or two, and ends with a concrete next step. "
            "Do not repeat the bullet list. Sound like a calm friend, not a compliance bot.",
        )
    )

    result = llm_gateway.generate(
        "coach",
        sections,
        language=language,
        user_id=user.id if user else None,
    )
    if result.ok:
        return {"mode": result.mode, "message": result.text}

    return {"mode": "offline", "message": _offline_message(items, ctx)}


# ---------------------------------------------------------------------------
# Deterministic fallbacks — used whenever the gateway is unavailable
# ---------------------------------------------------------------------------
def _clean_trade_message(
    side: str | None, symbol: str | None, quantity: float | None, language: str
) -> str:
    """Positive confirmation when no rule fires.

    "No interventions fired" is engine vocabulary and reads like an error to a
    beginner. Naming why the trade looked sound is the reinforcement half of the
    feedback loop.
    """
    if language == "hi":
        return (
            "Is trade par koi warning nahi hai. Aapka position size aur "
            "diversification theek lag rahe hain. Aage badhiye."
        )
    if side and symbol and quantity:
        verb = "buy" if side == "buy" else "sell"
        return (
            f"No warnings on this one. Your {verb} of {quantity:g} {symbol} sits within "
            f"sensible position-size and diversification limits, and it doesn't look like "
            f"a reaction to a price swing. This is what a considered trade looks like."
        )
    return (
        "No warnings on this one. Position size and diversification both look sensible. "
        "This is what a considered trade looks like."
    )


def _offline_message(items: list[dict], ctx: dict | None = None) -> str:
    """Templated fallback that still uses the context we already computed.

    Even without a model we can say something better than a bare rule dump: the
    repeat count and heed rate are plain Python facts.
    """
    primary = items[0]
    parts = [f"{primary['title']}. {primary['message']}"]

    if ctx:
        repeats = sum(ctx["times_ignored_these_rules"].values())
        if repeats >= 2:
            parts.append(
                f"You have traded through this warning {repeats} times before — "
                f"worth pausing on that pattern."
            )
        elif ctx["heed_rate_overall"] is not None and ctx["heed_rate_overall"] >= 0.80:
            parts.append("You usually heed these, so treat this as a quick check rather than a red flag.")

    extras = [f"Also: {i['title'].lower()}." for i in items[1:3]]
    if extras:
        parts.append(" ".join(extras))

    return " ".join(parts)
