"""Portfolio + trading endpoints with the intervention engine in the loop."""

import uuid

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import InterventionLog, User
from app.schemas import ConfirmTradeRequest, PreviewTradeRequest
from app.services import coach as coach_service
from app.services import indexer
from app.services import interventions as interventions_service
from app.services import llm_gateway
from app.services import portfolio as portfolio_service
from app.services import risk_reviewer
from app.services import valuation as valuation_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _get_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _priced_quote(db: Session, user: User, symbol: str) -> dict:
    """Resolve a scenario-adjusted quote, or fail cleanly.

    Every trade path needs a price, and without one there is no preview to give:
    no estimated cost, and several rules (concentration, cash drain, FOMO) have
    nothing to compare against. R13.2 forbids returning a partial preview, so this
    refuses the whole request rather than serving one with holes in it.

    ``get_quote`` already falls back to a stale cache before giving up, so a
    LookupError here means there is no price at all — not merely an old one. 503
    rather than 500: the market feed being unreachable is transient and worth
    retrying, and the learner deserves to be told which symbol failed instead of
    reading a stack trace.
    """
    try:
        return portfolio_service.quote_for_user(db, user, symbol)
    except LookupError as e:
        log.warning("Trade path could not price %s: %s", symbol, e)
        raise HTTPException(
            status_code=503,
            detail=(
                f"No live price available for {symbol} right now, so this trade "
                f"can't be checked. Please try again in a moment."
            ),
        ) from e


@router.get("/{user_id}")
def get_portfolio(user_id: str, db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    return portfolio_service.portfolio_snapshot(db, user)


@router.post("/preview")
def preview_trade(
    payload: PreviewTradeRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Run intervention checks WITHOUT executing the trade.

    Warnings are persisted here as ``pending`` under a fresh ``preview_id``.
    The frontend echoes that id back on confirm or cancel so we can record
    whether the learner heeded the advice — the signal the discipline
    sub-score is built on.
    """
    user = _get_user(db, payload.user_id)
    quote = _priced_quote(db, user, payload.symbol)
    fired = interventions_service.evaluate_pre_trade(
        db, user, payload.symbol, payload.side, payload.quantity
    )
    fired_dicts = [i.to_dict() for i in fired]

    preview_id = uuid.uuid4().hex
    if fired:
        interventions_service.log_interventions(
            db, user, fired, preview_id=preview_id, user_action="pending"
        )

    # db and user let the coach read this learner's history, so the same rule
    # reads differently for a repeat offender than for someone acting deliberately.
    coach_message = coach_service.coach_explain(
        fired_dicts,
        persona=user.persona,
        language=user.language,
        side=payload.side,
        symbol=quote["symbol"],
        quantity=payload.quantity,
        db=db,
        user=user,
    )
    # The AI portfolio review is supplementary, so it runs after this response is
    # sent (R13.1: rule findings must not wait on a model call). The frontend
    # fetches it from /preview/{preview_id}/ai-findings.
    #
    # The coach message above is deliberately NOT deferred: it is the primary
    # content of the modal, it is bounded by the gateway's 8-second timeout, and
    # it returns instantly when no key is configured. Deferring it would open the
    # modal with an empty explanation, which is worse for the learner than a
    # short wait.
    ai_pending = llm_gateway.is_available()
    if ai_pending:
        background.add_task(
            risk_reviewer.review_in_background,
            user.id,
            symbol=quote["symbol"],
            side=payload.side,
            quantity=payload.quantity,
            rule_findings=fired_dicts,
            preview_id=preview_id,
        )

    return {
        "preview_id": preview_id,
        "quote": quote,
        "interventions": fired_dicts,
        "coach": coach_message,
        "blocking": any(i["severity"] == "critical" for i in fired_dicts),
        "estimated_cost": round(float(quote["price"]) * payload.quantity, 2),
        # Tells the frontend whether to poll for AI findings at all.
        "ai_review_pending": ai_pending,
    }


@router.get("/preview/{preview_id}/ai-findings")
def preview_ai_findings(
    preview_id: str,
    user_id: str,
    db: Session = Depends(get_db),
):
    """Advisory AI findings for a preview.

    Separate from the preview response so the modal can render rule findings
    immediately. Returns ``status`` so the client can tell "still working" from
    "finished with nothing to add" — zero findings is a valid, reassuring answer.
    """
    user = _get_user(db, user_id)
    findings = risk_reviewer.findings_for_preview(db, user.id, preview_id)

    if findings:
        status = "ready"
    elif risk_reviewer.is_complete(preview_id):
        status = "ready"
    elif not llm_gateway.is_available():
        status = "unavailable"
    else:
        status = "pending"

    return {
        "preview_id": preview_id,
        "status": status,
        "findings": findings,
        # Restated on the wire so a client can never mistake these for scored rules.
        "affects_score": False,
    }


def _resolve_fired(db: Session, user: User, payload: ConfirmTradeRequest, side: str) -> list[dict]:
    """Return the warnings attached to this trade, marking them as ignored.

    When a ``preview_id`` is supplied we reuse the rows already written at
    preview time. That avoids a second full rule evaluation (which would mean
    another Yahoo history call for the FOMO rule) and guarantees the audit
    trail matches exactly what the learner was shown.
    """
    if payload.preview_id:
        rows = (
            db.query(InterventionLog)
            .filter(
                InterventionLog.user_id == user.id,
                InterventionLog.preview_id == payload.preview_id,
            )
            .all()
        )
        if rows:
            interventions_service.resolve_preview(db, user, payload.preview_id, "ignored")
            return [
                {
                    "rule_id": r.rule_id,
                    "severity": r.severity,
                    "title": r.title,
                    "message": r.message,
                    "concept": r.concept,
                    "context": r.context or {},
                }
                for r in rows
            ]
        return []

    # No preview id: a direct API call that skipped the coaching modal. Evaluate
    # now so the trade is still audited, and refuse it if a critical rule fires —
    # otherwise "blocking" would be trivially bypassable.
    fired = interventions_service.evaluate_pre_trade(
        db, user, payload.symbol, side, payload.quantity
    )
    if any(i.severity == "critical" for i in fired):
        raise HTTPException(
            status_code=409,
            detail=(
                "This trade triggers a critical warning. Call /portfolio/preview "
                "first and resubmit with its preview_id to acknowledge it."
            ),
        )
    if fired:
        new_id = uuid.uuid4().hex
        interventions_service.log_interventions(
            db, user, fired, preview_id=new_id, user_action="ignored"
        )
    return [i.to_dict() for i in fired]


@router.post("/buy")
def buy(payload: ConfirmTradeRequest, db: Session = Depends(get_db)):
    user = _get_user(db, payload.user_id)
    # Priced first: executing against a symbol we cannot price would either 500
    # mid-write or, worse, transact at a fallback figure.
    _priced_quote(db, user, payload.symbol)
    fired_dicts = _resolve_fired(db, user, payload, "buy")
    try:
        result = portfolio_service.execute_buy(
            db, user, payload.symbol, payload.quantity,
            interventions_fired=fired_dicts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    valuation_service.record_snapshot(db, user, reason="trade")
    indexer.refresh_corpus_b_safe(db, user)
    return _trade_response(result, fired_dicts)


@router.post("/sell")
def sell(payload: ConfirmTradeRequest, db: Session = Depends(get_db)):
    user = _get_user(db, payload.user_id)
    _priced_quote(db, user, payload.symbol)
    fired_dicts = _resolve_fired(db, user, payload, "sell")
    try:
        result = portfolio_service.execute_sell(
            db, user, payload.symbol, payload.quantity,
            interventions_fired=fired_dicts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    valuation_service.record_snapshot(db, user, reason="trade")
    indexer.refresh_corpus_b_safe(db, user)
    return _trade_response(result, fired_dicts)


def _trade_response(result, fired_dicts: list[dict]):
    return {
        "transaction": {
            "id": result.transaction.id,
            "symbol": result.transaction.symbol,
            "side": result.transaction.side,
            "quantity": result.transaction.quantity,
            "price": result.transaction.price,
            "fee": result.transaction.fee,
            "realised_pnl": result.transaction.realised_pnl,
        },
        "cash_after": result.cash_after,
        "holding_quantity": result.holding_quantity,
        "avg_cost": result.avg_cost,
        "interventions_fired": fired_dicts,
    }
