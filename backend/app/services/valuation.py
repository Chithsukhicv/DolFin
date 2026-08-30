"""Portfolio value timeline (the equity curve).

DolFin's central claim is that holding through a downturn beats panic-selling.
A number in a warning box asserts that; a curve *shows* it. Every trade and
every scenario transition writes a point here, so a learner who sat through a
simulated crash can look at their own chart afterwards and see the dip and the
recovery they lived through.

Points are deliberately event-driven rather than on a fixed clock: the
interesting moments are trades and scenario boundaries, and a background ticker
would cost a Yahoo call per user per interval for no extra teaching value.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import PortfolioSnapshot, User
from app.services import portfolio as portfolio_service

log = logging.getLogger(__name__)

# Skip writing a "poll" point if one already exists this recently, so repeated
# page loads don't flood the curve with duplicates.
MIN_POLL_GAP_SECONDS = 300


def record_snapshot(
    db: Session,
    user: User,
    *,
    reason: str = "poll",
    scenario_id: str | None = None,
) -> PortfolioSnapshot | None:
    """Append one point to the user's equity curve.

    Never raises: a failed snapshot must not break the trade that triggered it.
    """
    try:
        snap = portfolio_service.portfolio_snapshot(db, user)
    except Exception as e:
        log.warning("Could not value portfolio for %s: %s", user.id, e)
        return None

    invested = sum(h["quantity"] * h["avg_cost"] for h in snap["holdings"])

    point = PortfolioSnapshot(
        user_id=user.id,
        total_value=snap["total_value"],
        cash=snap["cash"],
        market_value=snap["market_value"],
        invested_cost=round(invested, 2),
        unrealised_pnl=snap.get("unrealised_pnl", 0.0),
        reason=reason,
        scenario_id=scenario_id,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return point


def record_poll(db: Session, user: User) -> PortfolioSnapshot | None:
    """Rate-limited snapshot for ordinary page views."""
    from datetime import datetime, timedelta, timezone

    latest = (
        db.query(PortfolioSnapshot)
        .filter_by(user_id=user.id)
        .order_by(PortfolioSnapshot.created_at.desc())
        .first()
    )
    if latest is not None:
        created = latest.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created < timedelta(seconds=MIN_POLL_GAP_SECONDS):
            return None
    return record_snapshot(db, user, reason="poll")


def equity_curve(db: Session, user: User, *, limit: int = 500) -> list[dict]:
    """Return the user's value timeline, oldest first."""
    rows = (
        db.query(PortfolioSnapshot)
        .filter_by(user_id=user.id)
        .order_by(PortfolioSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "at": r.created_at.isoformat(),
            "total_value": round(r.total_value, 2),
            "cash": round(r.cash, 2),
            "market_value": round(r.market_value, 2),
            "invested_cost": round(r.invested_cost, 2),
            "unrealised_pnl": round(r.unrealised_pnl, 2),
            "reason": r.reason,
            "scenario_id": r.scenario_id,
        }
        for r in rows
    ]
