"""Behavioural Intervention Engine.

Pre-trade and event-driven rules that fire before an order is confirmed.
The rule engine is deterministic and explainable. The optional AI layer
is *only* used to expand the message into a friendlier, persona-aware
explanation — never to decide whether a rule fires.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.data import stocks_seed
from app.models import Holding, InterventionLog, Stock, Transaction, User
from app.services import market as market_service
from app.services import portfolio as portfolio_service
from app.services import scenarios as scenarios_service

Severity = Literal["info", "warn", "critical"]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class Intervention:
    rule_id: str
    severity: Severity
    title: str
    message: str
    concept: str | None = None  # e.g. "diversification", "sip", "loss_aversion"
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "concept": self.concept,
            "context": _json_safe(self.context),
        }


def _json_safe(value):
    """Strip NaN and Infinity, which are not valid JSON.

    Rule context is built from market data, and market data arrives with gaps.
    One non-finite float used to fail serialisation of the entire preview
    response with an opaque 500, so this is a backstop: a slightly incomplete
    context is always better than a dead endpoint.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def evaluate_pre_trade(
    db: Session,
    user: User,
    symbol: str,
    side: Literal["buy", "sell"],
    quantity: float,
) -> list[Intervention]:
    """Run every applicable pre-trade rule and return the firings, ordered by severity."""
    snapshot = portfolio_service.portfolio_snapshot(db, user)
    quote = portfolio_service.quote_for_user(db, user, symbol)
    sym = quote["symbol"]

    stock = db.query(Stock).filter_by(symbol=sym).first()
    scenario = scenarios_service.active_scenario(db, user.id)

    fired: list[Intervention] = []

    if side == "buy":
        fired += _rule_concentration(snapshot, sym, stock, quote, quantity)
        fired += _rule_sector_overlap(snapshot, sym, stock, quote, quantity)
        fired += _rule_volatility_mismatch(user, stock)
        fired += _rule_fomo(sym, quote)
        fired += _rule_cash_drain(snapshot, quote, quantity)
        fired += _rule_buy_during_rally(scenario)
    else:  # sell
        fired += _rule_panic_sell(db, user, sym, quote, scenario)
        fired += _rule_loss_aversion_lock_in(snapshot, sym, quote, quantity)
        fired += _rule_long_horizon_short_hold(db, user, sym)

    # Sort: critical first, then warn, then info.
    weight = {"critical": 0, "warn": 1, "info": 2}
    fired.sort(key=lambda i: weight[i.severity])
    return fired


def log_interventions(
    db: Session,
    user: User,
    interventions: list[Intervention],
    *,
    preview_id: str,
    user_action: str = "pending",
) -> None:
    """Persist firings against a preview id.

    Called at *preview* time, before the user has decided anything. The rows
    start as ``pending`` and are later resolved by :func:`resolve_preview`.
    Logging at preview rather than execution is what makes "heeded" meaningful:
    a cancelled trade leaves no transaction behind, so if we only logged on
    execution there would be nothing to mark as heeded.
    """
    for it in interventions:
        db.add(InterventionLog(
            user_id=user.id,
            rule_id=it.rule_id,
            severity=it.severity,
            title=it.title,
            message=it.message,
            concept=it.concept,
            context=it.context,
            preview_id=preview_id,
            user_action=user_action,
        ))
    db.commit()


def resolve_preview(
    db: Session,
    user: User,
    preview_id: str,
    user_action: Literal["heeded", "ignored"],
) -> int:
    """Resolve every pending warning from one preview. Returns rows updated.

    Scoped to ``preview_id`` so confirming or cancelling can never rewrite the
    history of an earlier trade.
    """
    if not preview_id:
        return 0
    rows = (
        db.query(InterventionLog)
        .filter(
            InterventionLog.user_id == user.id,
            InterventionLog.preview_id == preview_id,
            InterventionLog.user_action == "pending",
        )
        .all()
    )
    for row in rows:
        row.user_action = user_action
    db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Buy-side rules
# ---------------------------------------------------------------------------
def _rule_concentration(
    snapshot: dict,
    sym: str,
    stock: Stock | None,
    quote: dict,
    quantity: float,
) -> list[Intervention]:
    """Single-stock concentration > 20% of market value after this trade.

    Index ETFs are exempt: each already holds dozens of companies, so warning a
    learner for putting 40% into a Nifty 50 fund would be teaching the opposite
    of the lesson. A higher bar still applies so an all-in position gets flagged.
    """
    is_basket = stocks_seed.is_diversified_instrument(sym)
    threshold = 0.60 if is_basket else 0.20
    price = float(quote["price"])
    add_value = price * quantity

    existing_value = next(
        (h["market_value"] for h in snapshot["holdings"] if h["symbol"] == sym),
        0.0,
    )

    # Position size is measured against the whole portfolio, cash included.
    # Measuring against invested value alone made every learner's first trade
    # read as "100% of your portfolio" and fire a critical warning, because at
    # that moment the one new holding was all the invested value there was.
    # A buy moves money from cash into an asset, so total value is unchanged.
    total_value = snapshot["total_value"]
    if total_value <= 0:
        return []
    new_position_pct = (existing_value + add_value) / total_value

    if new_position_pct < threshold:
        return []

    label = stock.name if stock else sym
    if is_basket:
        return [Intervention(
            rule_id="concentration",
            severity="info",
            title="Nearly everything in one fund",
            message=(
                f"After this trade, {label} would be {new_position_pct*100:.0f}% of your portfolio. "
                f"An index fund is already spread across many companies, so this is far safer than "
                f"the same weight in a single stock. Worth knowing it still leaves you tied to one "
                f"index and one market."
            ),
            concept="index_funds",
            context={"symbol": sym, "post_trade_pct": new_position_pct, "threshold": threshold,
                     "instrument": "index_fund"},
        )]

    return [Intervention(
        rule_id="concentration",
        severity="warn" if new_position_pct < 0.30 else "critical",
        title="High concentration in a single stock",
        message=(
            f"After this trade, {label} would be {new_position_pct*100:.0f}% of your portfolio. "
            f"A common rule of thumb is to keep any single stock under 20% so one company's "
            f"stumble can't sink your whole portfolio."
        ),
        concept="diversification",
        context={"symbol": sym, "post_trade_pct": new_position_pct, "threshold": threshold},
    )]


def _rule_sector_overlap(
    snapshot: dict,
    sym: str,
    stock: Stock | None,
    quote: dict,
    quantity: float,
) -> list[Intervention]:
    """Sector exposure > 40% after this trade."""
    if stock is None:
        return []
    threshold = 0.40
    price = float(quote["price"])
    add_value = price * quantity

    sector_value = sum(
        h["market_value"] for h in snapshot["holdings"] if h["sector"] == stock.sector
    )
    # Same reasoning as the concentration rule: weigh against the whole
    # portfolio including cash, not just what happens to be invested so far.
    total_value = snapshot["total_value"]
    if total_value <= 0:
        return []
    new_sector_pct = (sector_value + add_value) / total_value
    if new_sector_pct < threshold:
        return []

    return [Intervention(
        rule_id="sector_overlap",
        severity="warn",
        title=f"Heavy exposure to the {stock.sector} sector",
        message=(
            f"This trade pushes {stock.sector} to {new_sector_pct*100:.0f}% of your portfolio. "
            f"When one sector dominates, a single industry-wide problem hits everything you own. "
            f"Spread across at least 4–5 sectors."
        ),
        concept="diversification",
        context={"sector": stock.sector, "post_trade_pct": new_sector_pct, "threshold": threshold},
    )]


def _rule_volatility_mismatch(user: User, stock: Stock | None) -> list[Intervention]:
    """Low-risk users buying high-risk stocks."""
    if stock is None:
        return []
    if user.risk_appetite == "low" and stock.risk_level == "high":
        return [Intervention(
            rule_id="volatility_mismatch",
            severity="warn",
            title="Risk level higher than your profile",
            message=(
                f"You said you're a low-risk investor, but {stock.name} is a high-volatility stock. "
                f"Big swings in either direction are normal here — make sure you're prepared for it."
            ),
            concept="risk_appetite",
            context={"user_risk": user.risk_appetite, "stock_risk": stock.risk_level},
        )]
    if user.risk_appetite == "medium" and stock.risk_level == "high":
        return [Intervention(
            rule_id="volatility_mismatch",
            severity="info",
            title="Slightly higher volatility than your usual",
            message=(
                f"{stock.name} is a high-volatility stock. Keep position size small "
                f"so a bad week doesn't ruin your year."
            ),
            concept="risk_appetite",
            context={"user_risk": user.risk_appetite, "stock_risk": stock.risk_level},
        )]
    return []


def _rule_fomo(sym: str, quote: dict) -> list[Intervention]:
    """Fires when buying after a recent fast run-up (>15% over ~5 days)."""
    try:
        hist = market_service.get_history(sym, period="1mo")
    except Exception:
        return []
    if hist is None or "Close" not in hist:
        return []

    # Yahoo pads its series with NaN rows for non-trading days, and thinly
    # traded symbols can have gaps mid-series. Dropping them first matters more
    # than it looks: NaN fails every comparison, so `run < 0.15` was False and
    # the rule fired on a nan value — a spurious warning that also made the
    # response unserialisable.
    closes = hist["Close"].dropna()
    if len(closes) < 6:
        return []

    last = float(closes.iloc[-1])
    five_days_ago = float(closes.iloc[-6])
    if five_days_ago <= 0 or not math.isfinite(last) or not math.isfinite(five_days_ago):
        return []
    run = (last - five_days_ago) / five_days_ago
    if not math.isfinite(run) or run < 0.15:
        return []
    return [Intervention(
        rule_id="fomo",
        severity="warn",
        title="Buying after a fast run-up",
        message=(
            f"This stock is up {run*100:.1f}% in the last few days. Buying right after a sharp "
            f"rally often means paying near the local top. If you still want in, consider "
            f"smaller staggered buys instead of going all-in today."
        ),
        concept="fomo",
        context={"recent_run_pct": run},
    )]


def _rule_cash_drain(snapshot: dict, quote: dict, quantity: float) -> list[Intervention]:
    """Fires if cash buffer drops below 10% after the trade."""
    price = float(quote["price"])
    cost = price * quantity
    remaining_cash = snapshot["cash"] - cost
    new_total = snapshot["total_value"]  # value doesn't change with a buy (cash → asset)
    if new_total <= 0:
        return []
    cash_pct = remaining_cash / new_total
    if cash_pct >= 0.10:
        return []
    return [Intervention(
        rule_id="cash_drain",
        severity="info",
        title="Cash buffer running low",
        message=(
            f"After this trade, only {cash_pct*100:.0f}% of your portfolio would be in cash. "
            f"A small cash cushion is useful for buying opportunities and emergencies."
        ),
        concept="cash_management",
        context={"post_trade_cash_pct": cash_pct},
    )]


def _rule_buy_during_rally(scenario) -> list[Intervention]:
    """When a simulated rally is active, warn against piling in at the top."""
    if scenario is None or not scenario.is_active or scenario.kind != "rally":
        return []
    return [Intervention(
        rule_id="buy_during_rally",
        severity="info",
        title="Buying during a simulated rally",
        message=(
            "A rally scenario is running. Markets always look easiest near the top. "
            "Stick to your plan and avoid sizing up just because prices are rising."
        ),
        concept="market_cycles",
        context={"scenario_kind": scenario.kind},
    )]


# ---------------------------------------------------------------------------
# Sell-side rules
# ---------------------------------------------------------------------------
def _rule_panic_sell(
    db: Session,
    user: User,
    sym: str,
    quote: dict,
    scenario,
) -> list[Intervention]:
    """The headline rule: selling during a simulated crash/correction."""
    if scenario is None or not scenario.is_active:
        return []
    if scenario.kind not in ("crash", "correction"):
        return []

    holding = db.query(Holding).filter_by(user_id=user.id, symbol=sym).first()
    if holding is None or holding.quantity <= 0:
        return []

    drawdown_pct = abs(scenario.severity) * 100
    return [Intervention(
        rule_id="panic_sell",
        severity="critical",
        title="Selling during a simulated downturn",
        message=(
            f"You're about to sell {sym} during a simulated {scenario.kind} of about "
            f"{drawdown_pct:.0f}%. Historically, investors who sell during a crash lock in losses "
            f"that they would have recovered by simply holding. "
            f"This is exactly the moment to practise patience."
        ),
        concept="panic_selling",
        context={
            "scenario_kind": scenario.kind,
            "scenario_severity": scenario.severity,
            "scenario_id": scenario.id,
        },
    )]


def _rule_loss_aversion_lock_in(
    snapshot: dict,
    sym: str,
    quote: dict,
    quantity: float,
) -> list[Intervention]:
    """Selling at >10% loss outside a scenario — encourage reflection, not action."""
    holding_data = next((h for h in snapshot["holdings"] if h["symbol"] == sym), None)
    if not holding_data:
        return []
    pnl_pct = holding_data.get("unrealised_pnl_pct", 0.0)
    if pnl_pct >= -10.0:
        return []
    return [Intervention(
        rule_id="loss_lock_in",
        severity="warn",
        title="Locking in a sizeable loss",
        message=(
            f"This sell would lock in a {pnl_pct:.1f}% loss on {sym}. "
            f"Did the original reason for buying actually change, or is this an emotional sell? "
            f"If the company is still fundamentally fine, holding may be the better call."
        ),
        concept="loss_aversion",
        context={"unrealised_pnl_pct": pnl_pct},
    )]


def _rule_long_horizon_short_hold(db: Session, user: User, sym: str) -> list[Intervention]:
    """Selling within 7 days of buying — flag short-termism."""
    last_buy = (
        db.query(Transaction)
        .filter_by(user_id=user.id, symbol=sym, side="buy")
        .order_by(Transaction.created_at.desc())
        .first()
    )
    if last_buy is None:
        return []
    last_buy_at = last_buy.created_at
    if last_buy_at.tzinfo is None:
        last_buy_at = last_buy_at.replace(tzinfo=timezone.utc)
    held_for = datetime.now(timezone.utc) - last_buy_at
    if held_for >= timedelta(days=7):
        return []
    days = held_for.days + held_for.seconds / 86_400
    return [Intervention(
        rule_id="short_hold",
        severity="info",
        title="Selling shortly after buying",
        message=(
            f"You bought {sym} only {days:.1f} days ago. Frequent in-and-out trading "
            f"usually destroys returns through fees, taxes and bad timing. "
            f"Long-term investors win because they hold."
        ),
        concept="long_term_thinking",
        context={"held_days": days},
    )]
