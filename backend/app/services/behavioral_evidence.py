"""Verified, timestamped behavioural evidence used by Readiness V2.

Practice dates use UTC because the existing application stores UTC timestamps
and users do not have a persisted timezone preference. Multiple events on one
UTC date produce one practice day.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import QuizAttempt, Reflection, Transaction, User


def _utc(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    # SQLite returns the application's UTC timestamps without tzinfo. Treat
    # those legacy values as UTC; never use the host's local timezone.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _streaks(days: list[date], today: date) -> tuple[int, int]:
    if not days:
        return 0, 0
    ordered = sorted(set(days))
    longest = run = 0
    previous: date | None = None
    for day in ordered:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    latest = ordered[-1]
    if latest < today - timedelta(days=1):
        return 0, longest
    current = 1
    cursor = latest
    day_set = set(ordered)
    while cursor - timedelta(days=1) in day_set:
        cursor -= timedelta(days=1)
        current += 1
    return current, longest


def build_behavioral_evidence(
    db: Session, user: User, *, now: datetime | None = None
) -> dict:
    """Aggregate qualifying events without using AI output or page activity."""
    current_time = _utc(now or datetime.now(timezone.utc))
    assert current_time is not None
    today = current_time.date()

    event_sources: dict[date, set[str]] = defaultdict(set)
    trade_days: set[date] = set()
    recent_trade_days: set[date] = set()
    recent_trade_dates: list[date] = []
    daily_trades: dict[date, dict[str, float | int]] = defaultdict(
        lambda: {"trade_count": 0, "gross_value": 0.0}
    )
    transactions = db.query(Transaction).filter_by(user_id=user.id).all()
    valid_transactions = 0
    recent_transactions = 0
    recent_cutoff = today - timedelta(days=59)
    for txn in transactions:
        stamp = _utc(txn.created_at)
        try:
            quantity = float(txn.quantity or 0)
            price = float(txn.price or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            stamp is None or stamp.date() > today or not math.isfinite(quantity)
            or not math.isfinite(price) or quantity <= 0 or price <= 0
            or txn.side not in ("buy", "sell")
        ):
            continue
        day = stamp.date()
        valid_transactions += 1
        trade_days.add(day)
        if recent_cutoff <= day <= today:
            recent_transactions += 1
            recent_trade_days.add(day)
            recent_trade_dates.append(day)
        event_sources[day].add("trade")
        row = daily_trades[day]
        row["trade_count"] += 1
        try:
            notional = quantity * price
        except (TypeError, ValueError, OverflowError):
            notional = float("nan")
        if math.isfinite(notional) and notional > 0:
            row["gross_value"] += notional

    quizzes = db.query(QuizAttempt).filter_by(user_id=user.id).all()
    valid_quizzes = 0
    for quiz in quizzes:
        stamp = _utc(quiz.created_at)
        if stamp and stamp.date() <= today:
            event_sources[stamp.date()].add("quiz")
            valid_quizzes += 1

    reflections = db.query(Reflection).filter_by(user_id=user.id).all()
    valid_reflections = 0
    for reflection in reflections:
        stamp = _utc(reflection.created_at)
        # The persisted Reflection row is written at the review/cancellation
        # endpoint. Its optional free-text reason is not required to prove the
        # review happened, and is never read for scoring.
        if stamp and stamp.date() <= today:
            event_sources[stamp.date()].add("reflection")
            valid_reflections += 1

    # InterventionLog.created_at records preview time, not the later moment
    # the learner chose heeded/ignored. Do not use it to invent a practice date.

    practice_days = sorted(event_sources)
    current_streak, longest_streak = _streaks(practice_days, today)
    window_start = today - timedelta(days=29)
    recent_days = [day for day in practice_days if window_start <= day <= today]
    history_span = (
        (practice_days[-1] - practice_days[0]).days + 1 if len(practice_days) > 1 else 1
    )
    trade_span_days = (
        (max(trade_days) - min(trade_days)).days + 1 if len(trade_days) > 1 else 1
    )
    recent_trade_span_days = (
        (max(recent_trade_dates) - min(recent_trade_dates)).days + 1
        if len(recent_trade_dates) > 1 else 1
    )

    return {
        "timezone": "UTC",
        "qualifying_events": {
            "trades": valid_transactions,
            "completed_quizzes": valid_quizzes,
            "written_reflections": valid_reflections,
        },
        "practice_days": [day.isoformat() for day in practice_days],
        "practice_day_sources": {
            day.isoformat(): sorted(sources) for day, sources in sorted(event_sources.items())
        },
        "trade_days": [day.isoformat() for day in sorted(trade_days)],
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "rolling_30_day_practice_days": len(recent_days),
        "rolling_30_day_consistency_rate": round(len(recent_days) / 30.0, 4),
        "history_span_days": history_span,
        "trade_history_span_days": trade_span_days,
        "recent_trade_history_span_days": recent_trade_span_days,
        "lifetime_practice_days": len(practice_days),
        "lifetime_practice_rate": round(len(practice_days) / history_span, 4),
        "daily_trade_activity": [
            {
                "date": day.isoformat(),
                "trade_count": int(values["trade_count"]),
                "gross_value": round(float(values["gross_value"]), 2),
            }
            for day, values in sorted(daily_trades.items())
        ],
        "trade_count": valid_transactions,
        "trade_day_count": len(trade_days),
        "recent_trade_count": recent_transactions,
        "recent_trade_day_count": len(recent_trade_days),
        "practice_day_count": len(practice_days),
        "today": today.isoformat(),
    }
