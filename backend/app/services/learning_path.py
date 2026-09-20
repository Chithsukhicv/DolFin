"""The guided learning path, ordered by what this learner actually gets wrong.

A brand-new user previously landed on an empty dashboard with no indication of
what to do next, which is the single worst moment in the product for someone who
has never invested. The first version of this service fixed that with eight
ordered steps — but they were identical for everyone, which meant a learner who
diversifies well and panic-sells constantly was told to read about
diversification.

This version keeps the eight steps and adds two things:

- **remedial steps** targeting the concepts the learner has demonstrably not
  absorbed, measured by warnings they traded through and quizzes they failed
- **a rationale on every step** naming the evidence it was chosen from, so the
  path can explain itself rather than just reordering silently

Two properties are deliberately preserved. ``done`` is always computed from
application data with no model involvement, so progress can never regress
because an API call failed. And when the gateway is unavailable the original
eight steps are returned in their original order — a known-good sequence is a
better degraded state than a half-personalised one.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import (
    Goal,
    Holding,
    InterventionLog,
    KnowledgeChunk,
    QuizAttempt,
    Scenario,
    Stock,
    Transaction,
    User,
)
from app.services import llm_gateway
from app.services import readiness as readiness_service

log = logging.getLogger(__name__)

TARGET_HOLDINGS = 4
TARGET_SECTORS = 3
TARGET_QUIZZES = 3

# Weighting for the weakness score. An ignored warning is a decision the learner
# made against advice, which is stronger evidence of a missing idea than a failed
# quiz — a quiz can be failed by misreading the question.
IGNORED_WARNING_WEIGHT = 2.0
FAILED_QUIZ_WEIGHT = 1.0


def _step(
    key: str,
    title: str,
    description: str,
    done: bool,
    *,
    href: str,
    action: str,
    rationale: str,
    concept: str | None = None,
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
        # Names the learner evidence this step was selected from (R6.3).
        "rationale": rationale,
        "concept": concept,
    }
    if target is not None:
        step["current"] = current or 0
        step["target"] = target
    return step


# ---------------------------------------------------------------------------
# Measured weakness
# ---------------------------------------------------------------------------
def measure_weaknesses(db: Session, user: User) -> dict[str, dict]:
    """Per-concept evidence that the idea has not landed.

    All arithmetic, no judgement. Only *resolved* warnings count: a warning left
    pending means the learner closed the modal, which says nothing either way.
    """
    uid = user.id

    logs = (
        db.query(InterventionLog)
        .filter(InterventionLog.user_id == uid, InterventionLog.concept.isnot(None))
        .all()
    )
    attempts = db.query(QuizAttempt).filter_by(user_id=uid).all()

    passed = {a.concept for a in attempts if a.passed}

    out: dict[str, dict] = {}
    for log_row in logs:
        entry = out.setdefault(
            log_row.concept,
            {"ignored": 0, "heeded": 0, "fired": 0, "failed_quizzes": 0, "passed_quiz": False},
        )
        entry["fired"] += 1
        if log_row.user_action == "ignored":
            entry["ignored"] += 1
        elif log_row.user_action == "heeded":
            entry["heeded"] += 1

    for attempt in attempts:
        entry = out.setdefault(
            attempt.concept,
            {"ignored": 0, "heeded": 0, "fired": 0, "failed_quizzes": 0, "passed_quiz": False},
        )
        if not attempt.passed:
            entry["failed_quizzes"] += 1

    for concept, entry in out.items():
        entry["passed_quiz"] = concept in passed
        # A passed quiz does not erase ignored warnings — knowing the idea and
        # acting on it are different things, and the product cares about the
        # second one. But it does remove the "go learn this" step.
        entry["score"] = (
            entry["ignored"] * IGNORED_WARNING_WEIGHT
            + entry["failed_quizzes"] * FAILED_QUIZ_WEIGHT
        )

    return out


def _corpus_a_concepts(db: Session) -> set[str]:
    """Concepts that Corpus A can actually ground a step in (R6.8).

    Reads the index rather than the seed list, so a step is never suggested for
    a concept the chatbot and quiz generator have no material for. If the index
    has not been built yet, falls back to the seed library — Corpus A is derived
    from it deterministically, so the set is the same once indexed.
    """
    rows = (
        db.query(KnowledgeChunk.chunk_key)
        .filter(
            KnowledgeChunk.corpus == "A",
            KnowledgeChunk.chunk_key.like("concept:%"),
        )
        .all()
    )
    keys = {k.split(":")[1] for (k,) in rows if k.count(":") >= 2}
    if keys:
        return keys

    from app.data.concepts_seed import CONCEPTS

    log.debug("Corpus A not indexed; using the seed concept list for path grounding.")
    return {c["key"] for c in CONCEPTS}


def _remedial_steps(
    db: Session, weaknesses: dict[str, dict]
) -> list[dict]:
    """One step per concept the learner has demonstrably not absorbed."""
    from app.data.concepts_seed import get_concept

    available = _corpus_a_concepts(db)
    out: list[dict] = []

    ranked = sorted(
        (
            (concept, data)
            for concept, data in weaknesses.items()
            if data["score"] > 0 and concept in available
        ),
        key=lambda pair: -pair[1]["score"],
    )

    for concept, data in ranked:
        meta = get_concept(concept)
        if meta is None:
            continue

        bits: list[str] = []
        if data["ignored"]:
            bits.append(
                f"you traded through the {concept.replace('_', ' ')} warning "
                f"{data['ignored']} time(s)"
            )
        if data["failed_quizzes"]:
            bits.append(f"you did not pass its quiz {data['failed_quizzes']} time(s)")

        out.append(_step(
            f"fix:{concept}",
            f"Work on {meta['title'].lower()}",
            meta["one_liner"],
            data["passed_quiz"] and data["ignored"] == 0,
            href=f"/learn/{concept}",
            action="Read it, then take the quiz",
            rationale="Chosen because " + " and ".join(bits) + ".",
            concept=concept,
        ))

    return out


# ---------------------------------------------------------------------------
# The base eight
# ---------------------------------------------------------------------------
def _base_steps(db: Session, user: User) -> list[dict]:
    """The original ordered eight, with ``done`` computed from real data.

    The sequence is pedagogical: understand a concept, practise it small,
    diversify, face a downturn, then prove the lesson stuck. Facing the crash
    simulator comes only after the learner holds a few positions, because a crash
    is not instructive when there is nothing invested to watch fall.
    """
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

    symbols = [h.symbol for h in holdings]
    sectors: set[str] = set()
    if symbols:
        rows = db.query(Stock.sector).filter(Stock.symbol.in_(symbols)).all()
        sectors = {s for (s,) in rows if s}

    ever_scenario = (
        db.query(InterventionLog)
        .filter(InterventionLog.user_id == uid, InterventionLog.rule_id == "panic_sell")
        .count()
        > 0
    )
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

    return [
        _step(
            "goal",
            "Pick what you're investing for",
            "A goal gives every later decision something to be measured against.",
            goal_count > 0,
            href="/",
            action="Set a goal",
            rationale=(
                "Everyone starts here — nothing else can be judged without a target."
                if goal_count == 0
                else f"Done: you have {goal_count} goal(s) set."
            ),
        ),
        _step(
            "learn_basics",
            "Read how diversification works",
            "Five minutes here prevents the most common beginner mistake. No money involved.",
            passed_quizzes > 0 or len(buys) > 0,
            href="/learn/diversification",
            action="Read the concept",
            rationale=(
                "Suggested before your first trade so the first decision is an informed one."
                if not buys
                else "Done: you have started trading and using the library."
            ),
            concept="diversification",
        ),
        _step(
            "first_buy",
            "Make your first practice buy",
            "Real NSE prices, simulated money. Nothing here can cost you anything.",
            len(buys) > 0,
            href="/market",
            action="Browse the market",
            rationale=(
                "You have not placed a buy yet."
                if not buys
                else f"Done: {len(buys)} buy(s) placed."
            ),
        ),
        _step(
            "diversify",
            f"Hold {TARGET_HOLDINGS} stocks across {TARGET_SECTORS} sectors",
            "Spreading out is the difference between one bad company hurting you and ruining you.",
            len(holdings) >= TARGET_HOLDINGS and len(sectors) >= TARGET_SECTORS,
            href="/market",
            action="Add a different sector",
            rationale=(
                f"You hold {len(holdings)} position(s) across {len(sectors)} sector(s); "
                f"the target is {TARGET_HOLDINGS} across {TARGET_SECTORS}."
            ),
            concept="diversification",
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
            rationale=(
                "You have never run a scenario, so you have not seen your own curve fall."
                if not (scenario_started or ever_scenario)
                else "Done: you have run at least one scenario."
            ),
            concept="market_cycles",
        ),
        _step(
            "hold_through",
            "Hold through the downturn",
            "When the panic-sell warning fires, choose to reflect instead of selling. That's the whole lesson.",
            held_through,
            href="/portfolio",
            action="See your holdings",
            rationale=(
                "You have not yet backed out of a sell during a downturn."
                if not held_through
                else "Done: you have held through at least one simulated downturn."
            ),
            concept="panic_selling",
        ),
        _step(
            "prove_it",
            f"Pass {TARGET_QUIZZES} concept quizzes",
            "Short checks that the ideas actually landed, not just that you clicked through them.",
            passed_quizzes >= TARGET_QUIZZES,
            href="/learn",
            action="Open the library",
            rationale=f"You have passed {passed_quizzes} of {TARGET_QUIZZES} quizzes.",
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
            rationale=(
                f"Your score is {readiness['score']:.0f}; graduation is at "
                f"{readiness['graduation_threshold']:.0f}."
            ),
            current=int(readiness["score"]),
            target=int(readiness["graduation_threshold"]),
        ),
    ]


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def _assemble(steps: list[dict], *, adaptive: bool, weaknesses: dict) -> dict:
    completed = sum(1 for s in steps if s["done"])
    total = len(steps)
    next_step = next((s for s in steps if not s["done"]), None)
    return {
        "steps": steps,
        "completed": completed,
        "total": total,
        "percent": round(completed / total * 100) if total else 0,
        "next_step": next_step,
        "all_done": completed == total,
        "adaptive": adaptive,
        "weaknesses": weaknesses,
    }


def _safe_fallback(db: Session, user: User) -> dict:
    """R6.7: something in the computation blew up — return a usable skeleton.

    Every ``done`` is false, which understates progress but never invents it, and
    ``next_step`` is the first step so the UI still has somewhere to point.
    """
    steps = [
        _step(
            key, title, description, False,
            href=href, action=action,
            rationale="Progress could not be computed right now.",
            concept=concept,
        )
        for key, title, description, href, action, concept in (
            ("goal", "Pick what you're investing for",
             "A goal gives every later decision something to be measured against.",
             "/", "Set a goal", None),
            ("learn_basics", "Read how diversification works",
             "Five minutes here prevents the most common beginner mistake. No money involved.",
             "/learn/diversification", "Read the concept", "diversification"),
            ("first_buy", "Make your first practice buy",
             "Real NSE prices, simulated money. Nothing here can cost you anything.",
             "/market", "Browse the market", None),
            ("diversify", f"Hold {TARGET_HOLDINGS} stocks across {TARGET_SECTORS} sectors",
             "Spreading out is the difference between one bad company hurting you and ruining you.",
             "/market", "Add a different sector", "diversification"),
            ("face_crash", "Live through a simulated crash",
             "Watch your own portfolio fall 30%. This is the rehearsal that makes the real thing survivable.",
             "/scenarios", "Start a crash", "market_cycles"),
            ("hold_through", "Hold through the downturn",
             "When the panic-sell warning fires, choose to reflect instead of selling. That's the whole lesson.",
             "/portfolio", "See your holdings", "panic_selling"),
            ("prove_it", f"Pass {TARGET_QUIZZES} concept quizzes",
             "Short checks that the ideas actually landed, not just that you clicked through them.",
             "/learn", "Open the library", None),
            ("graduate", "Reach a Readiness Score of 80",
             "The point at which your habits, not your luck, suggest you're ready for real money.",
             "/readiness", "Check your score", None),
        )
    ]
    return {
        "steps": steps,
        "completed": 0,
        "total": len(steps),
        "percent": 0,
        "next_step": steps[0],
        "all_done": False,
        "adaptive": False,
        "weaknesses": {},
        "degraded": True,
    }


def build_path(db: Session, user: User) -> dict:
    """Compute the learner's path. Never raises."""
    try:
        return _build(db, user)
    except Exception as e:
        log.warning("Learning path computation failed for %s: %s", user.id, e)
        return _safe_fallback(db, user)


def _build(db: Session, user: User) -> dict:
    base = _base_steps(db, user)
    weaknesses = measure_weaknesses(db, user)

    # R6.6: without the gateway, serve the known-good fixed sequence rather than
    # a partially personalised one.
    if not llm_gateway.is_available():
        return _assemble(base, adaptive=False, weaknesses=weaknesses)

    steps = base + _remedial_steps(db, weaknesses)

    # Score every step by the weakness of the concept it addresses, then sort:
    # unfinished work first, worst weakness first, original order as the
    # tie-break. A learner with no ignored warnings scores zero everywhere and
    # therefore sees the original sequence — the adaptation only bites once
    # there is evidence to adapt to.
    def sort_key(pair: tuple[int, dict]) -> tuple:
        index, step = pair
        concept = step.get("concept")
        score = weaknesses.get(concept, {}).get("score", 0.0) if concept else 0.0
        return (1 if step["done"] else 0, -score, index)

    ordered = [step for _, step in sorted(enumerate(steps), key=sort_key)]
    return _assemble(ordered, adaptive=True, weaknesses=weaknesses)
