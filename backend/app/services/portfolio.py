"""Virtual portfolio engine: buy/sell, holdings, valuation, P&L."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Holding, Stock, Transaction, User
from app.services import market as market_service
from app.services import scenarios as scenarios_service

# Brokerage fee in basis points (0.05% per side). Tweakable; matches discount-broker reality.
FEE_BPS = 5.0


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------
def get_or_create_user(db: Session, email: str, *, persona: str = "woman", display_name: str | None = None) -> User:
    user = db.query(User).filter_by(email=email).first()
    if user:
        return user
    user = User(email=email, persona=persona, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_user_portfolio(db: Session, user: User, *, starting_cash: float = 100_000.0) -> User:
    """Wipe holdings and transactions, restore starting cash."""
    db.query(Holding).filter_by(user_id=user.id).delete()
    db.query(Transaction).filter_by(user_id=user.id).delete()
    user.cash = starting_cash
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Quote (scenario-aware)
# ---------------------------------------------------------------------------
def quote_for_user(db: Session, user: User, symbol: str) -> dict:
    base = market_service.get_quote(symbol)
    scenario = scenarios_service.active_scenario(db, user.id)
    return scenarios_service.adjust_quote_dict(base.__dict__, scenario)


# ---------------------------------------------------------------------------
# Buy / Sell
# ---------------------------------------------------------------------------
@dataclass
class TradeResult:
    transaction: Transaction
    cash_after: float
    holding_quantity: float
    avg_cost: float


def execute_buy(
    db: Session,
    user: User,
    symbol: str,
    quantity: float,
    *,
    interventions_fired: list[dict] | None = None,
) -> TradeResult:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    quote = quote_for_user(db, user, symbol)
    price = float(quote["price"])
    sym = quote["symbol"]

    gross = price * quantity
    fee = gross * (FEE_BPS / 10_000)
    total_cost = gross + fee

    if total_cost > user.cash + 1e-6:
        raise ValueError(
            f"Insufficient cash: need ₹{total_cost:,.2f}, have ₹{user.cash:,.2f}"
        )

    # Update holding (volume-weighted average cost basis).
    holding = db.query(Holding).filter_by(user_id=user.id, symbol=sym).first()
    if holding is None:
        holding = Holding(user_id=user.id, symbol=sym, quantity=0.0, avg_cost=0.0)
        db.add(holding)

    new_qty = holding.quantity + quantity
    holding.avg_cost = ((holding.avg_cost * holding.quantity) + (price * quantity)) / new_qty
    holding.quantity = new_qty

    user.cash -= total_cost

    scenario = scenarios_service.active_scenario(db, user.id)
    txn = Transaction(
        user_id=user.id,
        symbol=sym,
        side="buy",
        quantity=quantity,
        price=price,
        fee=fee,
        scenario_id=scenario.id if scenario else None,
        interventions_fired=interventions_fired or [],
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return TradeResult(txn, user.cash, holding.quantity, holding.avg_cost)


def execute_sell(
    db: Session,
    user: User,
    symbol: str,
    quantity: float,
    *,
    interventions_fired: list[dict] | None = None,
) -> TradeResult:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    quote = quote_for_user(db, user, symbol)
    price = float(quote["price"])
    sym = quote["symbol"]

    holding = db.query(Holding).filter_by(user_id=user.id, symbol=sym).first()
    if holding is None or holding.quantity < quantity - 1e-6:
        have = holding.quantity if holding else 0.0
        raise ValueError(f"Cannot sell {quantity} {sym}: only {have} held")

    gross = price * quantity
    fee = gross * (FEE_BPS / 10_000)
    proceeds = gross - fee
    realised = (price - holding.avg_cost) * quantity - fee

    holding.quantity -= quantity
    if holding.quantity < 1e-6:
        # Wipe the holding cleanly when fully sold.
        db.delete(holding)
        new_qty, new_avg = 0.0, 0.0
    else:
        new_qty, new_avg = holding.quantity, holding.avg_cost

    user.cash += proceeds

    scenario = scenarios_service.active_scenario(db, user.id)
    txn = Transaction(
        user_id=user.id,
        symbol=sym,
        side="sell",
        quantity=quantity,
        price=price,
        fee=fee,
        realised_pnl=realised,
        scenario_id=scenario.id if scenario else None,
        interventions_fired=interventions_fired or [],
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return TradeResult(txn, user.cash, new_qty, new_avg)


# ---------------------------------------------------------------------------
# Read-side: portfolio snapshot, valuation, allocation
# ---------------------------------------------------------------------------
def portfolio_snapshot(db: Session, user: User) -> dict:
    holdings = db.query(Holding).filter_by(user_id=user.id).all()
    scenario = scenarios_service.active_scenario(db, user.id)

    enriched = []
    invested = 0.0
    market_value = 0.0
    sector_alloc: dict[str, float] = {}

    stale_count = 0
    for h in holdings:
        # A failed quote must not make the position disappear. Dropping it here
        # would understate total value and silently distort the diversification
        # and readiness scores, so we fall back to cost basis and flag the row.
        price_unavailable = False
        try:
            base = market_service.get_quote(h.symbol)
            adj = scenarios_service.adjust_quote_dict(base.__dict__, scenario)
            live_price = float(adj["price"])
            price_stale = bool(getattr(base, "stale", False))
        except Exception:
            live_price = h.avg_cost
            price_stale = True
            price_unavailable = True

        if price_stale:
            stale_count += 1

        cost_basis = h.avg_cost * h.quantity
        position_value = live_price * h.quantity
        unrealised = position_value - cost_basis

        invested += cost_basis
        market_value += position_value

        stock = db.query(Stock).filter_by(symbol=h.symbol).first()
        sector = stock.sector if stock else "Unknown"
        sector_alloc[sector] = sector_alloc.get(sector, 0.0) + position_value

        enriched.append({
            "symbol": h.symbol,
            "name": stock.name if stock else h.symbol,
            "sector": sector,
            "quantity": h.quantity,
            "avg_cost": h.avg_cost,
            "live_price": live_price,
            "cost_basis": cost_basis,
            "market_value": position_value,
            "unrealised_pnl": unrealised,
            "unrealised_pnl_pct": (unrealised / cost_basis * 100.0) if cost_basis else 0.0,
            # Surfaced so the UI can mark the row instead of showing a stale or
            # cost-based figure as if it were a live price.
            "price_stale": price_stale,
            "price_unavailable": price_unavailable,
        })

    total_value = user.cash + market_value
    sector_alloc_pct = {
        sector: (value / market_value * 100.0) if market_value else 0.0
        for sector, value in sector_alloc.items()
    }

    return {
        "user_id": user.id,
        "cash": user.cash,
        "invested": invested,
        "market_value": market_value,
        "total_value": total_value,
        "unrealised_pnl": market_value - invested,
        "holdings": enriched,
        "sector_allocation_pct": sector_alloc_pct,
        # Non-zero means at least one position is priced off cached or cost data.
        "stale_price_count": stale_count,
        "scenario": (
            {
                "id": scenario.id,
                "kind": scenario.kind,
                "severity": scenario.severity,
                "narrative": scenario.narrative,
                "multiplier": scenarios_service.current_multiplier(scenario),
            }
            if scenario
            else None
        ),
    }
