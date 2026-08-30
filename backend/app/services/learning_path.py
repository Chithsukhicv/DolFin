"""The guided learning path.

A brand-new user previously landed on an empty dashboard with no indication of
what to do next, which is the single worst moment in the product for someone who
has never invested. This service turns the whole platform into an ordered set of
steps computed from what the learner has actually done, so there is always one
obvious next action.

The ordering is deliberate: understand a concept, then practise it small, then
diversify, then face a downturn, then prove the lesson stuck. Facing the crash
simulator comes only after the learner holds a few positions, because a crash is
not instructive when there is nothing invested to watch fall.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Goal, Holding, InterventionLog, QuizAttempt, Transaction, User
from app.services import readiness as readiness_service
from app.services import scenarios as scenarios_service

TARGET_HOLDINGS = 4
TARGET_SECTORS = 3
TARGET_QUIZZES = 3


def _step(
    key: str,
    title: str,
    description: str,
    done: bool,
    *,
    href: str,
    action: str,
    current: int | None = None,
    target: int | None = None,
) -> dict:
    step = {
        "key": key,
        "title": title,
        "description": description,
        "done": done,
        "href": href,
        "action": action,
    }
    if target is not None:
        step["current"] = current or 0
        step["target"] = target
    return step


def build_path(db: Session, user: User) -> dict:
    """Compute the learner's progress through the guided path."""
    uid = user.id

    goal_count = db.query(Goal).filter_by(user_id=uid).count()
    txns = db.query(Transaction).filter_by(user_id=uid).all()
    buys = [t for t in txns if t.side == "buy"]
    holdings = db.query(Holding).filter_by(user_id=uid).all()

    passed_quizzes = (
        db.query(QuizAttempt.concept)
        .filter(QuizAttempt.user_id == uid, QuizAttempt.passed.is_(True))
        .distinct()
        .count()
    )

    # Distinct sectors held, resolved through the stock catalogue.
    from app.models import Stock

    symbols = [h.symbol for h in holdings]
    sectors = set()
    if symbols:
        rows = db.query(Stock.sector).filter(Stock.symbol.in_(symbols)).all()
        sectors = {s for (s,) in rows if s}

    # Has the learner ever experienced a scenario, and did they hold through one?
    ever_scenario = (
        db.query(InterventionLog)
        .filter(InterventionLog.user_id == uid, InterventionLog.rule_id == "panic_sell")
        .count()
        > 0
    )
    from app.models import Scenario

    scenario_started = db.query(Scenario).filter_by(user_id=uid).count() > 0

    held_through = (
        db.query(InterventionLog)
        .filter(
            InterventionLog.user_id == uid,
            InterventionLog.rule_id == "panic_sell",
            InterventionLog.user_action == "heeded",
        )
        .count()
        > 0
    )

    readiness = readiness_service.compute_readiness(db, user)
    graduated = readiness["graduated"]

    steps = [
        _step(
            "goal",
            "Pick what you're investing for",
            "A goal gives every later decision something to be measured against.",
            goal_count > 0,
            href="/",
            action="Set a goal",
        ),
        _step(
            "learn_basics",
            "Read how diversification works",
            "Five minutes here prevents the most common beginner mistake. No money involved.",
            passed_quizzes > 0 or len(buys) > 0,
            href="/learn/diversification",
            action="Read the concept",
        ),
        _step(
            "first_buy",
            "Make your first practice buy",
            "Real NSE prices, simulated money. Nothing here can cost you anything.",
            len(buys) > 0,
            href="/market",
            action="Browse the market",
        ),
        _step(
            "diversify",
            f"Hold {TARGET_HOLDINGS} stocks across {TARGET_SECTORS} sectors",
            "Spreading out is the difference between one bad company hurting you and ruining you.",
            len(holdings) >= TARGET_HOLDINGS and len(sectors) >= TARGET_SECTORS,
            href="/market",
            action="Add a different sector",
            current=min(len(holdings), TARGET_HOLDINGS),
            target=TARGET_HOLDINGS,
        ),
        _step(
            "face_crash",
            "Live through a simulated crash",
            "Watch your own portfolio fall 30%. This is the rehearsal that makes the real thing survivable.",
            scenario_started or ever_scenario,
            href="/scenarios",
            action="Start a crash",
        ),
        _step(
            "hold_through",
            "Hold through the downturn",
            "When the panic-sell warning fires, choose to reflect instead of selling. That's the whole lesson.",
            held_through,
            href="/portfolio",
            action="See your holdings",
        ),
        _step(
            "prove_it",
            f"Pass {TARGET_QUIZZES} concept quizzes",
            "Short checks that the ideas actually landed, not just that you clicked through them.",
            passed_quizzes >= TARGET_QUIZZES,
            href="/learn",
            action="Open the library",
            current=min(passed_quizzes, TARGET_QUIZZES),
            target=TARGET_QUIZZES,
        ),
        _step(
            "graduate",
            "Reach a Readiness Score of 80",
            "The point at which your habits, not your luck, suggest you're ready for real money.",
            graduated,
            href="/readiness",
            action="Check your score",
            current=int(readiness["score"]),
            target=int(readiness["graduation_threshold"]),
        ),
    ]

    completed = sum(1 for s in steps if s["done"])
    next_step = next((s for s in steps if not s["done"]), None)

    return {
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "percent": round(completed / len(steps) * 100),
        "next_step": next_step,
        "all_done": completed == len(steps),
    }
