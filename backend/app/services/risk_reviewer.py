"""Second-opinion portfolio review at trade time.

The nine deterministic rules each check one measurable threshold. That makes them
reproducible and testable, but it also means they can only see what someone
thought to encode. This reviewer looks at the whole portfolio, the goal, and the
proposed trade together, and names risks that no single threshold expresses:

- five holdings in five different sectors that are all export-dependent, so the
  portfolio is really one bet on the rupee
- sector spread that looks fine while every holding is high-beta
- a goal eight months away funded entirely by small-caps
- buying back into a symbol the learner has already sold twice at a loss

Findings are advisory. They carry ``source="ai"``, live in ``ai_findings`` rather
than ``intervention_logs``, and never reach the Readiness Score — so the metric
stays reproducible even though the review does not.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.models import AIFinding, Goal, Stock, Transaction, User
from app.services import llm_gateway, retrieval
from app.services.llm_gateway import PromptSection

log = logging.getLogger(__name__)

MAX_FINDINGS = 3
_SEVERITIES = {"info", "warn", "critical"}


_TASK = """\
Review this portfolio and the proposed trade. Your job is to find concerns the
listed rules did NOT already raise. Look especially for:

- correlated exposure: holdings in different sectors that nonetheless rise and
  fall together (shared dependence on exports, the rupee, commodity prices,
  interest rates, or one end customer)
- aggregate volatility: sector spread that looks diversified while every holding
  is high-risk
- goal-horizon mismatch: the goal's timeframe versus the risk of the resulting
  portfolio
- repeat behaviour: buying back into a symbol previously sold at a loss

Rules:
- Do NOT restate any concern already listed under "Rules that already fired".
- Return between 0 and 3 findings. Zero is a valid and useful answer.
- Base every finding on the supplied numbers. Do not invent holdings or prices.
- Never tell the learner to buy or sell anything.

Return ONLY valid JSON, no prose, no code fences:
{"findings": [{"title": "short label, under 8 words",
               "body": "2-3 sentences addressed to the learner as 'you'",
               "severity": "info|warn|critical",
               "concept": "related concept key or null",
               "confidence": "high|medium|low"}]}"""


def _goal_brief(db: Session, user: User) -> str:
    """The learner's goals and horizons.

    Required for the goal-horizon findings in R2.3: "a goal eight months away
    funded entirely by small-caps" is only expressible if the model knows the
    horizon. Every figure is computed here, not by the model.
    """
    goals = db.query(Goal).filter_by(user_id=user.id).all()
    if not goals:
        return "The learner has not set a goal yet, so there is no horizon to judge risk against."

    lines = []
    for g in goals:
        years = g.horizon_months / 12
        band = (
            "short — a downturn may not have time to recover"
            if g.horizon_months <= 12
            else "medium" if g.horizon_months <= 60
            else "long — there is time to ride out volatility"
        )
        lines.append(
            f"- {g.label}: Rs {g.target_amount:,.0f} in {g.horizon_months} months "
            f"({years:.1f} years, horizon is {band})"
        )
    shortest = min(g.horizon_months for g in goals)
    lines.append(f"Shortest horizon across all goals: {shortest} months.")
    return "\n".join(lines)


def _portfolio_brief(db: Session, user: User, snapshot: dict) -> str:
    """Facts for the prompt. Computed in Python — the model does no arithmetic."""
    total = snapshot["total_value"] or 1.0
    lines = [
        f"Total portfolio value: Rs {snapshot['total_value']:,.0f} "
        f"(cash Rs {snapshot['cash']:,.0f}, invested Rs {snapshot['invested']:,.0f})",
        f"Cash is {snapshot['cash'] / total * 100:.0f}% of the portfolio",
        f"Risk appetite: {user.risk_appetite}",
    ]

    if snapshot["holdings"]:
        lines.append("Holdings:")
        for h in snapshot["holdings"]:
            stock = db.query(Stock).filter_by(symbol=h["symbol"]).first()
            risk = stock.risk_level if stock else "unknown"
            band = stock.market_cap_band if stock else "unknown"
            lines.append(
                f"  - {h['symbol']} ({h['sector']}, {band}-cap, {risk} risk): "
                f"{h['market_value'] / total * 100:.0f}% of portfolio, "
                f"unrealised P&L {h['unrealised_pnl_pct']:+.1f}%"
            )
    else:
        lines.append("Holdings: none yet")

    if snapshot.get("sector_allocation_pct"):
        alloc = ", ".join(
            f"{s} {p:.0f}%" for s, p in snapshot["sector_allocation_pct"].items()
        )
        lines.append(f"Sector split of invested value: {alloc}")

    if snapshot.get("scenario"):
        sc = snapshot["scenario"]
        lines.append(
            f"A simulated {sc['kind']} is active (severity {sc['severity']}, "
            f"price multiplier {sc['multiplier']:.2f})"
        )

    return "\n".join(lines)


def _trade_history_brief(db: Session, user: User, symbol: str) -> str:
    """Prior activity in this specific symbol — the repeat-trading signal."""
    rows = (
        db.query(Transaction)
        .filter_by(user_id=user.id, symbol=symbol)
        .order_by(Transaction.created_at.desc())
        .limit(8)
        .all()
    )
    if not rows:
        return "The learner has never traded this symbol before."

    losses = [t for t in rows if t.side == "sell" and (t.realised_pnl or 0) < 0]
    parts = [
        f"Prior trades in {symbol}: "
        + "; ".join(
            f"{t.side} {t.quantity:g} at Rs {t.price:,.2f}"
            + (f" (realised Rs {t.realised_pnl:,.0f})" if t.side == "sell" else "")
            for t in rows
        )
    ]
    if losses:
        parts.append(
            f"They have sold {symbol} at a loss {len(losses)} time(s) previously."
        )
    return " ".join(parts)


def _parse_findings(text: str, already_raised: set[str]) -> list[dict]:
    """Validate and filter the model's findings.

    Anything malformed is dropped rather than shown. A partial list of good
    findings is better than one hallucinated one.
    """
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    raw = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        if not title or len(body) < 20:
            continue
        # Don't repeat what a rule already said (R2.4).
        if any(term and term in title.lower() for term in already_raised):
            continue

        severity = str(item.get("severity", "info")).strip().lower()
        out.append({
            "title": title[:120],
            "body": body,
            "severity": severity if severity in _SEVERITIES else "info",
            "concept": (str(item.get("concept")).strip() or None)
            if item.get("concept") not in (None, "null", "")
            else None,
            "confidence": str(item.get("confidence", "medium")).strip().lower(),
        })
        if len(out) >= MAX_FINDINGS:
            break
    return out


def review(
    db: Session,
    user: User,
    *,
    snapshot: dict,
    symbol: str,
    side: str,
    quantity: float,
    rule_findings: list[dict],
    preview_id: str,
) -> list[dict]:
    """Run the review and persist findings. Returns [] when unavailable.

    Never raises — a failed review must not break the trade preview.
    """
    try:
        return _review(
            db, user, snapshot=snapshot, symbol=symbol, side=side,
            quantity=quantity, rule_findings=rule_findings, preview_id=preview_id,
        )
    except Exception as e:
        log.warning("Risk review failed for %s: %s", user.id, e)
        return []


def _review(
    db: Session,
    user: User,
    *,
    snapshot: dict,
    symbol: str,
    side: str,
    quantity: float,
    rule_findings: list[dict],
    preview_id: str,
) -> list[dict]:
    if not llm_gateway.is_available():
        return []

    already = {f.get("rule_id", "") for f in rule_findings}
    already |= {(f.get("concept") or "") for f in rule_findings}
    already = {a for a in already if a}

    fired_text = (
        "\n".join(f"- {f['rule_id']}: {f['title']}" for f in rule_findings)
        or "(none — no rule fired on this trade)"
    )

    # Ground the review in the concept library so findings cite DolFin's own
    # material rather than inventing a rationale.
    evidence = retrieval.retrieve(
        db,
        f"portfolio risk correlated exposure diversification {side} {symbol}",
        user_id=user.id,
        corpus="A",
        top_k=4,
    )

    sections = [
        PromptSection("Proposed trade", f"{side} {quantity:g} units of {symbol}"),
        PromptSection("Portfolio", _portfolio_brief(db, user, snapshot)),
        PromptSection("What the learner is saving for", _goal_brief(db, user)),
        PromptSection("History in this symbol", _trade_history_brief(db, user, symbol)),
        PromptSection("Rules that already fired", fired_text),
        PromptSection("Reference material", evidence.as_evidence() or "(none)"),
        PromptSection("Task", _TASK),
    ]

    result = llm_gateway.generate(
        "risk_review", sections, language=user.language, user_id=user.id
    )
    if not result.ok:
        return []

    findings = _parse_findings(result.text, already)
    citations = evidence.citations()

    for f in findings:
        db.add(AIFinding(
            user_id=user.id,
            preview_id=preview_id,
            kind="risk_review",
            severity=f["severity"],
            title=f["title"],
            body=f["body"],
            concept=f["concept"],
            confidence=f["confidence"],
            citations=citations,
            source="ai",
        ))
    if findings:
        db.commit()

    return [{**f, "source": "ai", "citations": citations} for f in findings]


def findings_for_preview(db: Session, user_id: str, preview_id: str) -> list[dict]:
    """Fetch stored findings so the UI can poll after the preview returns."""
    rows = (
        db.query(AIFinding)
        .filter_by(user_id=user_id, preview_id=preview_id, kind="risk_review")
        .order_by(AIFinding.created_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "severity": r.severity,
            "concept": r.concept,
            "confidence": r.confidence,
            "citations": r.citations or [],
            "source": r.source,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Deferred execution
# ---------------------------------------------------------------------------
# The trade preview must return rule findings without waiting for a model call
# (R13.1), so the review runs after the response is sent and the frontend fetches
# it separately. This tracks which previews have finished so the fetch endpoint
# can distinguish "still working" from "finished, found nothing" — an important
# difference, because zero findings is a valid and reassuring answer.
_completed: dict[str, float] = {}
_COMPLETION_TTL = 900.0


def _mark_complete(preview_id: str) -> None:
    import time

    now = time.time()
    _completed[preview_id] = now
    # Opportunistic cleanup so this cannot grow without bound.
    for key, stamp in list(_completed.items()):
        if now - stamp > _COMPLETION_TTL:
            del _completed[key]


def is_complete(preview_id: str) -> bool:
    return preview_id in _completed


def reset_completion_state() -> None:
    _completed.clear()


def review_in_background(
    user_id: str,
    *,
    symbol: str,
    side: str,
    quantity: float,
    rule_findings: list[dict],
    preview_id: str,
) -> None:
    """Entry point for FastAPI's BackgroundTasks.

    Opens its own session: the request's session is closed by the time this runs.
    Marks the preview complete on every path, including failure, so the frontend
    stops waiting rather than spinning forever.
    """
    from app.db import SessionLocal
    from app.services import portfolio as portfolio_service

    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None:
                return
            snapshot = portfolio_service.portfolio_snapshot(db, user)
            review(
                db, user,
                snapshot=snapshot, symbol=symbol, side=side, quantity=quantity,
                rule_findings=rule_findings, preview_id=preview_id,
            )
    except Exception as e:
        log.warning("Background risk review failed (preview=%s): %s", preview_id, e)
    finally:
        _mark_complete(preview_id)
