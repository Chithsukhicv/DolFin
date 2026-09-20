"""Names recurring patterns across a learner's entire history.

A rule sees one trade. This sees all of them, and that difference is the point:

    "You've sold four times in three weeks, and every one was within two days of
     a dip of 5% or more. Your buying is genuinely well diversified across five
     sectors — the issue isn't your stock picking, it's that dips make you flinch."

No threshold produces that sentence. It requires reading across time, separating
what the learner does well from what they repeat badly, and saying it in a way
that lands. That is synthesis, which is what a language model is actually good at.

Every number in the output is computed in Python and handed to the model as
ground truth, because the model is good at phrasing and unreliable at arithmetic.
Results are cached against the record counts they were computed from, so the page
does not pay for a model call until the learner's history actually changes.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Holding,
    InterventionLog,
    PatternAnalysis,
    QuizAttempt,
    Reflection,
    Stock,
    Transaction,
    User,
)
from app.services import llm_gateway, retrieval
from app.services.llm_gateway import PromptSection

log = logging.getLogger(__name__)

# Below this there is nothing to find, and guessing would be worse than saying so.
MIN_TRADES = 3
MIN_RESOLVED_WARNINGS = 1
MAX_PATTERNS = 3


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _counts(db: Session, user: User) -> dict:
    """The cache fingerprint. If none of these change, the analysis still holds."""
    resolved = (
        db.query(InterventionLog)
        .filter(
            InterventionLog.user_id == user.id,
            InterventionLog.user_action.in_(("heeded", "ignored")),
        )
        .count()
    )
    return {
        "txn_count": db.query(Transaction).filter_by(user_id=user.id).count(),
        "resolved_intervention_count": resolved,
        "quiz_attempt_count": db.query(QuizAttempt).filter_by(user_id=user.id).count(),
        "reflection_count": db.query(Reflection).filter_by(user_id=user.id).count(),
    }


def build_evidence(db: Session, user: User) -> dict:
    """Counted facts about this learner. All arithmetic happens here, not in the model."""
    txns = (
        db.query(Transaction)
        .filter_by(user_id=user.id)
        .order_by(Transaction.created_at.asc())
        .all()
    )
    logs = db.query(InterventionLog).filter_by(user_id=user.id).all()
    holdings = db.query(Holding).filter_by(user_id=user.id).all()
    attempts = db.query(QuizAttempt).filter_by(user_id=user.id).all()

    sells = [t for t in txns if t.side == "sell"]
    buys = [t for t in txns if t.side == "buy"]

    # Sells that happened while a scenario was running — the flinch signal.
    sells_in_scenario = [t for t in sells if t.scenario_id]

    # Holding period per sell, using the most recent prior buy of that symbol.
    hold_days: list[float] = []
    for sell in sells:
        prior = [
            t for t in buys
            if t.symbol == sell.symbol
            and _aware(t.created_at) <= _aware(sell.created_at)
        ]
        if prior:
            delta = _aware(sell.created_at) - _aware(prior[-1].created_at)
            hold_days.append(round(delta.total_seconds() / 86_400, 1))

    sectors: set[str] = set()
    for h in holdings:
        stock = db.query(Stock).filter_by(symbol=h.symbol).first()
        if stock:
            sectors.add(stock.sector)

    resolved = [l for l in logs if l.user_action in ("heeded", "ignored")]
    by_concept: dict[str, dict[str, int]] = {}
    for l in logs:
        entry = by_concept.setdefault(
            l.concept or "other", {"fired": 0, "heeded": 0, "ignored": 0}
        )
        entry["fired"] += 1
        if l.user_action in entry:
            entry[l.user_action] += 1

    span_days = None
    if len(txns) >= 2:
        span_days = round(
            (_aware(txns[-1].created_at) - _aware(txns[0].created_at)).total_seconds()
            / 86_400,
            1,
        )

    return {
        "trades": len(txns),
        "buys": len(buys),
        "sells": len(sells),
        "activity_span_days": span_days,
        "sells_during_a_scenario": len(sells_in_scenario),
        "holding_periods_days": hold_days,
        "sells_within_7_days": sum(1 for d in hold_days if d < 7),
        "holdings": len(holdings),
        "distinct_sectors": len(sectors),
        "sector_names": sorted(sectors),
        "realised_pnl": round(sum(t.realised_pnl or 0.0 for t in sells), 2),
        "warnings_fired": len(logs),
        "warnings_resolved": len(resolved),
        "warnings_heeded": sum(1 for l in resolved if l.user_action == "heeded"),
        "by_concept": by_concept,
        "quizzes_passed": sorted({a.concept for a in attempts if a.passed}),
        "quizzes_failed": sorted({a.concept for a in attempts if not a.passed}),
    }


def _evidence_lines(ev: dict) -> str:
    """Render the counted facts as prompt lines.

    Only facts that exist are included. Handing the model a line reading
    "sells during a scenario: 0" invites it to write a paragraph about something
    that never happened.
    """
    lines = [
        f"- Trades placed: {ev['trades']} ({ev['buys']} buys, {ev['sells']} sells)",
    ]
    if ev["activity_span_days"] is not None:
        lines.append(
            f"- All of that activity happened across {ev['activity_span_days']} days"
        )
    if ev["sells"]:
        lines.append(
            f"- Realised profit or loss across all sells: Rs {ev['realised_pnl']:,.2f}"
        )
    if ev["sells_during_a_scenario"]:
        lines.append(
            f"- Sold {ev['sells_during_a_scenario']} time(s) while a simulated "
            f"downturn or rally was running"
        )
    if ev["holding_periods_days"]:
        lines.append(
            f"- Holding periods before selling, in days: "
            f"{', '.join(str(d) for d in ev['holding_periods_days'])}"
        )
        if ev["sells_within_7_days"]:
            lines.append(
                f"- {ev['sells_within_7_days']} of those sells came within 7 days of buying"
            )
    lines.append(
        f"- Currently holds {ev['holdings']} position(s) across "
        f"{ev['distinct_sectors']} sector(s)"
        + (f": {', '.join(ev['sector_names'])}" if ev["sector_names"] else "")
    )
    lines.append(
        f"- Warnings: {ev['warnings_fired']} fired, {ev['warnings_resolved']} resolved, "
        f"{ev['warnings_heeded']} heeded"
    )
    for concept, counts in ev["by_concept"].items():
        lines.append(
            f"- The {concept.replace('_', ' ')} warning fired {counts['fired']} time(s): "
            f"heeded {counts['heeded']}, traded through {counts['ignored']}"
        )
    if ev["quizzes_passed"]:
        lines.append(f"- Quizzes passed: {', '.join(ev['quizzes_passed'])}")
    if ev["quizzes_failed"]:
        lines.append(f"- Quizzes attempted but not passed: {', '.join(ev['quizzes_failed'])}")
    return "\n".join(lines)


def heed_rates(ev: dict) -> dict[str, float]:
    """Per-concept heed rate over resolved warnings only.

    Unresolved warnings mean the learner closed the modal, which is neither good
    nor bad behaviour — counting them either way would misreport the habit.
    """
    out: dict[str, float] = {}
    for concept, counts in ev["by_concept"].items():
        resolved = counts["heeded"] + counts["ignored"]
        if resolved:
            out[concept] = round(counts["heeded"] / resolved, 2)
    return out


_TASK = """\
Name the recurring patterns in this learner's behaviour. You are looking across
their whole history, not at one trade — that breadth is the entire value here.

Rules:
- Return between 1 and 3 patterns.
- Every pattern's evidence list must contain at least one of the counted facts
  supplied above, quoted with its number and the time window it covers.
- Use ONLY the numbers supplied. Do not compute new ones and do not estimate.
- At least one pattern must name something the learner does WELL if any of the
  facts above support it. Someone told only what they get wrong stops reading.
- Separate the mechanics from the behaviour where the facts allow it: "your
  stock picking is fine, the problem is what you do when prices fall" is far more
  useful than "you are bad at investing".
- Do not tell the learner to buy or sell anything. Suggested actions should be
  habits, concepts to read, or things to notice about themselves.

Return ONLY valid JSON, no prose, no code fences:
{"patterns": [{"label": "the habit named in under 10 words",
               "evidence": ["counted fact with its number", "..."],
               "insight": "2-3 sentences addressed to the learner as 'you'",
               "next_action": "one concrete thing to do or notice",
               "concept": "related concept key or null",
               "is_strength": true or false}]}"""


def _parse(text: str) -> list[dict] | None:
    """Extract and validate the pattern list.

    Strict about contents, lenient about the envelope — models wrap JSON in code
    fences and preamble often enough that rejecting on that alone throws away
    good output.
    """
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("patterns")
    if not isinstance(raw, list):
        return None

    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        insight = str(item.get("insight", "")).strip()
        if not label or len(insight) < 20:
            continue
        evidence = [
            str(e).strip() for e in (item.get("evidence") or []) if str(e).strip()
        ]
        if not evidence:
            # R5.4: a pattern with no counted fact behind it is an opinion.
            continue
        concept = item.get("concept")
        out.append({
            "label": label[:120],
            "evidence": evidence[:4],
            "insight": insight,
            "next_action": str(item.get("next_action", "")).strip() or None,
            "concept": str(concept).strip() if concept not in (None, "", "null") else None,
            "is_strength": bool(item.get("is_strength")),
            "source": "ai",
        })
        if len(out) >= MAX_PATTERNS:
            break

    return out or None


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------
def _fallback_patterns(ev: dict) -> list[dict]:
    """A counted summary for when no model is available.

    Not as readable as the generated version, but it is the same facts, and the
    page stays useful with no API key. Ordered worst-habit-first, then strengths,
    because the thing to work on should be at the top.
    """
    rates = heed_rates(ev)
    patterns: list[dict] = []

    # --- weaknesses, worst first ------------------------------------------
    ignored = sorted(
        ((c, counts["ignored"]) for c, counts in ev["by_concept"].items() if counts["ignored"]),
        key=lambda pair: -pair[1],
    )
    for concept, count in ignored[:2]:
        label = concept.replace("_", " ")
        patterns.append({
            "label": f"Repeatedly trading through {label} warnings",
            "evidence": [
                f"The {label} warning fired {ev['by_concept'][concept]['fired']} time(s) "
                f"and you traded through it {count} time(s)"
                + (
                    f" across {ev['activity_span_days']} days"
                    if ev["activity_span_days"] is not None else ""
                ),
            ],
            "insight": (
                f"You have overridden the {label} warning {count} time(s). Once is a "
                f"judgement call. A repeated override is a habit, and habits are what "
                f"the Readiness Score is actually measuring."
            ),
            "next_action": f"Read the {label} concept page before your next trade.",
            "concept": concept,
            "is_strength": False,
            "source": "ai",
        })

    if ev["sells_within_7_days"] >= 2:
        patterns.append({
            "label": "Selling soon after buying",
            "evidence": [
                f"{ev['sells_within_7_days']} of your {ev['sells']} sells happened "
                f"within 7 days of the matching buy"
            ],
            "insight": (
                "Short holding periods mean brokerage and short-term capital gains tax "
                "take a bite before any thesis has had time to play out. The holding "
                "period is one of the few things about returns you fully control."
            ),
            "next_action": "Before selling, check whether the reason you bought has changed.",
            "concept": "long_term_thinking",
            "is_strength": False,
            "source": "ai",
        })

    if ev["sells_during_a_scenario"] >= 1:
        patterns.append({
            "label": "Selling into simulated downturns",
            "evidence": [
                f"{ev['sells_during_a_scenario']} of your sells happened while a "
                f"simulated market event was running"
            ],
            "insight": (
                "Selling while prices are falling converts a paper loss into a realised "
                "one and takes you out of the recovery. This is the single most "
                "expensive habit the simulator exists to catch."
            ),
            "next_action": "Next crash, do nothing for a day and watch what the curve does.",
            "concept": "panic_selling",
            "is_strength": False,
            "source": "ai",
        })

    # --- strengths (R5.5) -------------------------------------------------
    strong = sorted(
        ((c, r) for c, r in rates.items() if r >= 0.50), key=lambda pair: -pair[1]
    )
    for concept, rate in strong[:1]:
        label = concept.replace("_", " ")
        counts = ev["by_concept"][concept]
        patterns.append({
            "label": f"Listening to {label} warnings",
            "evidence": [
                f"You heeded the {label} warning {counts['heeded']} of "
                f"{counts['heeded'] + counts['ignored']} times it was resolved "
                f"({int(rate * 100)}%)"
            ],
            "insight": (
                f"You back out when the {label} warning fires more often than not. "
                f"That is the behaviour that separates someone ready for real money "
                f"from someone who is not. Keep it."
            ),
            "next_action": "Nothing to change here.",
            "concept": concept,
            "is_strength": True,
            "source": "ai",
        })

    if ev["distinct_sectors"] >= 3:
        patterns.append({
            "label": "Spreading money across sectors",
            "evidence": [
                f"Your {ev['holdings']} holdings sit across {ev['distinct_sectors']} "
                f"sectors: {', '.join(ev['sector_names'])}"
            ],
            "insight": (
                "Your allocation is genuinely spread out, so no single industry's bad "
                "year can dominate your outcome. Stock picking is not your weak point."
            ),
            "next_action": "Nothing to change here.",
            "concept": "diversification",
            "is_strength": True,
            "source": "ai",
        })

    if not patterns:
        # Enough activity to analyse, but nothing repeated yet. Say that rather
        # than inventing a habit from a handful of rows.
        patterns.append({
            "label": "No repeated habit yet",
            "evidence": [
                f"{ev['trades']} trades and {ev['warnings_resolved']} resolved "
                f"warnings so far"
            ],
            "insight": (
                "Nothing in your record repeats often enough yet to call it a pattern. "
                "That is a good sign this early — it means no single mistake has become "
                "a habit."
            ),
            "next_action": "Keep trading and check back after a few more decisions.",
            "concept": None,
            "is_strength": True,
            "source": "ai",
        })

    return patterns[:MAX_PATTERNS]


def _insufficient(ev: dict) -> dict:
    """R5.6 / R5.10: not enough record to analyse, and no model call made."""
    return {
        "status": "insufficient_activity",
        "message": (
            "There isn't enough history to find a pattern yet. Place a few trades and "
            "respond to at least one warning, then come back — patterns need "
            "repetition to be real rather than coincidence."
        ),
        "patterns": [],
        "evidence": ev,
        "mode": "skipped",
        "trades_needed": max(0, MIN_TRADES - ev["trades"]),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def analyse(db: Session, user: User, *, force: bool = False) -> dict:
    """Return this learner's behavioural patterns.

    Never raises. Order of decisions matters and is deliberate:

    1. Not enough history -> say so, make no model call. Checked *first*, so the
       insufficiency answer is identical whether or not a key is configured
       (R5.10).
    2. Cached analysis still valid -> return it, make no model call (R5.8).
    3. Model available -> generate, validate, persist.
    4. Anything else -> deterministic counted summary (R5.9).
    """
    try:
        return _analyse(db, user, force=force)
    except Exception as e:
        log.warning("Pattern analysis failed for %s: %s", user.id, e)
        return {
            "status": "unavailable",
            "message": "Pattern analysis could not be computed right now.",
            "patterns": [],
            "evidence": {},
            "mode": "offline",
        }


def _analyse(db: Session, user: User, *, force: bool) -> dict:
    counts = _counts(db, user)
    evidence = build_evidence(db, user)

    # 1. Too little to go on.
    if (
        evidence["trades"] < MIN_TRADES
        and counts["resolved_intervention_count"] < MIN_RESOLVED_WARNINGS
    ):
        return _insufficient(evidence)

    # 2. Cache: valid while every fingerprint count is unchanged.
    cached = (
        db.query(PatternAnalysis)
        .filter_by(user_id=user.id)
        .order_by(PatternAnalysis.created_at.desc())
        .first()
    )
    if cached is not None and not force and all(
        getattr(cached, field) == value for field, value in counts.items()
    ):
        return {
            "status": "ok",
            "message": None,
            "patterns": cached.patterns or [],
            "evidence": evidence,
            "mode": "cached",
            "generated_at": cached.created_at.isoformat(),
        }

    # 3. Generate.
    patterns: list[dict] | None = None
    mode = "offline"
    citations: list[dict] = []

    if llm_gateway.is_available():
        # Ground the advice in DolFin's own material so the suggested next action
        # points at a concept page that actually exists.
        weak = sorted(
            ev_concepts(evidence), key=lambda pair: -pair[1]
        )
        query = " ".join(c for c, _ in weak[:3]) or "behavioural investing habits"
        retrieved = retrieval.retrieve(
            db, f"{query} behavioural pattern habit", user_id=user.id, corpus="A", top_k=5
        )
        citations = retrieved.citations()

        sections = [
            PromptSection(
                "Who this is",
                f"A {user.persona} learner with a {user.risk_appetite} risk appetite "
                f"using a practice portfolio.",
            ),
            PromptSection("Counted facts about their record", _evidence_lines(evidence)),
            PromptSection("Reference material", retrieved.as_evidence() or "(none)"),
            PromptSection("Task", _TASK),
        ]
        result = llm_gateway.generate(
            "pattern", sections, language=user.language, user_id=user.id
        )
        if result.ok:
            patterns = _parse(result.text)
            if patterns:
                mode = result.mode
            else:
                log.warning("Pattern response failed validation for %s; using fallback.", user.id)

    # 4. Fallback.
    if not patterns:
        patterns = _fallback_patterns(evidence)
        mode = "offline"
        citations = []

    # R5.5 backstop: if the model returned only criticism while the record shows
    # a concept heeded at least half the time, add the strength ourselves rather
    # than re-prompting.
    if not any(p["is_strength"] for p in patterns):
        strengths = [
            p for p in _fallback_patterns(evidence) if p["is_strength"]
        ]
        if strengths:
            patterns = patterns[: MAX_PATTERNS - 1] + strengths[:1]

    for p in patterns:
        p["citations"] = citations

    row = PatternAnalysis(
        user_id=user.id,
        patterns=patterns,
        mode=mode,
        **counts,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "status": "ok",
        "message": None,
        "patterns": patterns,
        "evidence": evidence,
        "mode": mode,
        "generated_at": row.created_at.isoformat(),
    }


def ev_concepts(ev: dict) -> list[tuple[str, int]]:
    """(concept, ignored count) pairs — used to focus retrieval on weak spots."""
    return [(c, counts["ignored"]) for c, counts in ev["by_concept"].items()]
