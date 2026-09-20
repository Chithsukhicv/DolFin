"""Generates fresh quiz questions for the concepts a learner keeps missing.

The seeded bank has three questions per concept. Fail loss aversion twice and you
have memorised the answers rather than the idea, which makes the third attempt
measure recall instead of understanding. Generating new questions from the same
source material fixes that without writing hundreds of questions by hand.

The risk with generated assessment is obvious: a model can produce a question
with two correct answers, four identical options, or an answer index pointing at
nothing. So every question passes structural validation and a quality check
before a learner ever sees it, and anything that fails is replaced by a seeded
question rather than shown. A slightly repetitive quiz is a much better failure
than a wrong one.

Answers never leave the server. Each question the learner is shown is persisted
and referenced by id, so scoring reads the stored answer rather than trusting the
client — the Readiness Score depends on a passed quiz meaning something.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.data.quizzes_seed import quizzes_for_concept
from app.models import GeneratedQuestion, QuizAttempt, User
from app.services import llm_gateway, retrieval
from app.services.llm_gateway import PromptSection

log = logging.getLogger(__name__)

QUESTIONS_PER_QUIZ = 3
OPTION_COUNT = 4

# Quality thresholds (R8.6).
MAX_QUESTION_CHARS = 200
MAX_OPTION_CHARS = 120
MIN_EXPLANATION_CHARS = 20

# Ask for more than we need so failures can be dropped without falling back to
# seeded questions for the whole quiz.
GENERATION_TARGET = 5


# Tokens that count as naming or paraphrasing each concept (R8.6). Without this
# the check would only accept the literal concept key, which almost no
# well-written question contains.
_CONCEPT_TOKENS: dict[str, set[str]] = {
    "diversification": {"diversif", "spread", "concentrat", "single stock", "one company", "sector"},
    "panic_selling": {"panic", "crash", "falling", "fell", "downturn", "sell", "selling", "dip"},
    "fomo": {"fomo", "missing out", "run up", "ran up", "rally", "rallied", "surge", "hype", "chasing"},
    "loss_aversion": {"loss", "losses", "aversion", "break even", "breakeven", "hold on to", "red"},
    "long_term_thinking": {"long term", "long-term", "compound", "frequent trading", "holding period", "time in the market"},
    "risk_appetite": {"risk", "volatil", "appetite", "tolerance", "swing"},
    "cash_management": {"cash", "buffer", "liquidity", "emergency", "forced seller"},
    "market_cycles": {"cycle", "bull", "bear", "rally", "correction", "top", "bottom", "market"},
    "sip": {"sip", "systematic", "rupee cost", "rupee-cost", "averaging", "monthly", "schedule"},
    "index_funds": {"index", "etf", "nifty", "sensex", "whole market", "passive"},
}


def _concept_tokens(concept: str) -> set[str]:
    """Tokens that count as naming the concept.

    The curated set wins where one exists. Deriving tokens from the key as well
    would weaken the check: splitting ``index_funds`` yields "funds", which any
    question mentioning mutual funds would satisfy regardless of topic.
    """
    curated = _CONCEPT_TOKENS.get(concept)
    if curated:
        return set(curated)
    return {part for part in concept.split("_") if len(part) > 3}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_question(item: object, concept: str) -> dict | None:
    """Return a cleaned question, or None if it fails any check.

    Structural checks first (R8.2), then the quality checks (R8.6). Returning
    None rather than raising keeps the caller's discard-and-substitute loop
    simple.
    """
    if not isinstance(item, dict):
        return None

    question = str(item.get("question", "")).strip()
    explanation = str(item.get("explanation", "")).strip()
    raw_options = item.get("options")

    # --- structure --------------------------------------------------------
    if not question or not isinstance(raw_options, list):
        return None
    options = [str(o).strip() for o in raw_options]
    if len(options) != OPTION_COUNT or any(not o for o in options):
        return None
    try:
        answer = int(item.get("answer"))
    except (TypeError, ValueError):
        return None
    if not 0 <= answer < OPTION_COUNT:
        return None

    # --- quality (R8.6) ---------------------------------------------------
    if len(question) > MAX_QUESTION_CHARS:
        return None
    if len({o.lower() for o in options}) != OPTION_COUNT:
        return None
    if any(len(o) > MAX_OPTION_CHARS for o in options):
        return None
    if len(explanation) < MIN_EXPLANATION_CHARS:
        return None

    haystack = f"{question} {' '.join(options)}".lower()
    if not any(token in haystack for token in _concept_tokens(concept)):
        return None

    return {
        "question": question,
        "options": options,
        "answer": answer,
        "explanation": explanation,
    }


def _parse(text: str, concept: str) -> list[dict]:
    """Extract questions from the model response, discarding anything invalid."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    raw = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    discarded = 0
    for item in raw:
        cleaned = validate_question(item, concept)
        if cleaned is None:
            discarded += 1
            continue
        out.append(cleaned)
    if discarded:
        log.info("Discarded %d generated question(s) for %s.", discarded, concept)
    return out


# ---------------------------------------------------------------------------
# What the learner has already seen
# ---------------------------------------------------------------------------
def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def answered_correctly(db: Session, user: User, concept: str) -> set[str]:
    """Normalised text of questions this learner has already got right (R8.10).

    Re-asking a question someone already answered correctly measures memory, not
    understanding, so those are excluded from a generated set.
    """
    attempts = db.query(QuizAttempt).filter_by(user_id=user.id, concept=concept).all()
    seen: set[str] = set()
    for attempt in attempts:
        for row in attempt.answers or []:
            if isinstance(row, dict) and row.get("is_correct"):
                seen.add(_normalise(str(row.get("question", ""))))
    return {s for s in seen if s}


def failed_concepts(db: Session, user: User) -> list[str]:
    """Concepts the learner has attempted and not passed, most-failed first."""
    attempts = db.query(QuizAttempt).filter_by(user_id=user.id).all()
    passed = {a.concept for a in attempts if a.passed}
    failures: dict[str, int] = {}
    for attempt in attempts:
        if not attempt.passed and attempt.concept not in passed:
            failures[attempt.concept] = failures.get(attempt.concept, 0) + 1
    return [c for c, _ in sorted(failures.items(), key=lambda p: -p[1])]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
_TASK = """\
Write {count} multiple-choice questions that test whether the learner understands
this concept, using ONLY the reference material above.

Rules:
- Each question must have exactly 4 options and exactly 1 correct option.
- "answer" is the zero-based index of the correct option.
- Test the idea, not recall of a definition: describe a situation and ask what it
  shows or what the sensible response is.
- Wrong options must be plausible mistakes a beginner would actually make, not
  obviously silly.
- Keep each question under 200 characters and each option under 120 characters.
- The explanation must say why the correct option is correct in at least one full
  sentence.
- Use Indian context and rupees where an example needs money.
- Do not reference a specific real company as something to buy or sell.
- Avoid repeating any question listed under "Already answered correctly".

Return ONLY valid JSON, no prose, no code fences:
{{"questions": [{{"question": "...", "options": ["a","b","c","d"],
                 "answer": 0, "explanation": "..."}}]}}"""


def generate(db: Session, user: User, concept: str) -> tuple[list[dict], list[dict]]:
    """Generate and validate questions. Returns (questions, citations).

    Returns an empty list rather than raising whenever generation is impossible,
    so the caller can substitute seeded questions.
    """
    if not llm_gateway.is_available():
        return [], []

    # R8.3 — grounded in the concept's own Corpus A material.
    evidence = retrieval.retrieve(
        db, concept.replace("_", " "), user_id=user.id, corpus="A", top_k=6
    )
    if evidence.is_empty:
        log.info("No Corpus A material for %s; cannot generate questions.", concept)
        return [], []

    already = answered_correctly(db, user, concept)
    already_text = (
        "\n".join(f"- {q}" for q in list(already)[:8]) if already else "(none)"
    )

    sections = [
        PromptSection("Target concept", concept.replace("_", " ")),
        PromptSection("Reference material", evidence.as_evidence()),
        PromptSection("Already answered correctly", already_text),
        PromptSection("Task", _TASK.format(count=GENERATION_TARGET)),
    ]

    result = llm_gateway.generate(
        "quiz_gen", sections, language=user.language, user_id=user.id
    )
    if not result.ok:
        return [], []

    questions = [
        q for q in _parse(result.text, concept)
        if _normalise(q["question"]) not in already
    ]
    return questions, evidence.citations()


# ---------------------------------------------------------------------------
# Quiz assembly
# ---------------------------------------------------------------------------
def _persist(
    db: Session,
    user: User,
    concept: str,
    question: dict,
    citations: list[dict],
) -> GeneratedQuestion:
    row = GeneratedQuestion(
        user_id=user.id,
        concept=concept,
        question=question["question"],
        options=question["options"],
        answer=question["answer"],
        explanation=question["explanation"],
        citations=citations,
    )
    db.add(row)
    return row


def build_quiz(db: Session, user: User, concept: str) -> dict:
    """Assemble the quiz this learner will actually be shown.

    Generated questions first, seeded questions substituted for every slot
    generation could not fill (R8.7). Both kinds are persisted, so scoring can
    read the answer from the server rather than trusting the client.

    Returns ``{"status": "unavailable"}`` when neither source can supply a single
    question, which the router turns into a 422 naming the concept (R8.8).
    """
    seeded = quizzes_for_concept(concept)
    generated, citations = generate(db, user, concept)

    chosen: list[tuple[dict, str]] = [(q, "generated") for q in generated[:QUESTIONS_PER_QUIZ]]

    # R8.7 / R8.9 — fill the rest from the seed bank.
    if len(chosen) < QUESTIONS_PER_QUIZ:
        used = {_normalise(q["question"]) for q, _ in chosen}
        for item in seeded:
            if len(chosen) >= QUESTIONS_PER_QUIZ:
                break
            if _normalise(item["question"]) in used:
                continue
            cleaned = {
                "question": item["question"],
                "options": list(item["options"]),
                "answer": item["answer"],
                "explanation": item.get("explanation", ""),
            }
            chosen.append((cleaned, "seeded"))
            used.add(_normalise(item["question"]))

    # R8.8 — nothing available from either source.
    if not chosen:
        return {"status": "unavailable", "concept": concept}

    rows = [_persist(db, user, concept, q, citations if src == "generated" else [])
            for q, src in chosen]
    db.commit()
    for row in rows:
        db.refresh(row)

    generated_count = sum(1 for _, src in chosen if src == "generated")
    return {
        "status": "ok",
        "concept": concept,
        "mode": "generated" if generated_count else "seeded",
        "generated_count": generated_count,
        "seeded_count": len(chosen) - generated_count,
        "citations": citations if generated_count else [],
        "question_ids": [row.id for row in rows],
        "questions": [
            {
                "index": i,
                "id": row.id,
                "question": row.question,
                "options": row.options,
                "source": src,
            }
            for i, (row, (_, src)) in enumerate(zip(rows, chosen))
        ],
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score(
    db: Session,
    user: User,
    concept: str,
    question_ids: list[str],
    answers: list[int],
) -> dict | None:
    """Score a quiz built by ``build_quiz``.

    Reads each answer from the persisted row, so a client cannot report a pass it
    did not earn. Returns None when any id is unknown or belongs to someone else.
    """
    from app.services.quizzes import PASS_THRESHOLD_PCT

    rows: list[GeneratedQuestion] = []
    for qid in question_ids:
        row = db.get(GeneratedQuestion, qid)
        if row is None or row.user_id != user.id or row.concept != concept:
            return None
        rows.append(row)

    if not rows:
        return None

    correct = 0
    detail = []
    for i, row in enumerate(rows):
        given = answers[i] if i < len(answers) else -1
        is_correct = given == row.answer
        if is_correct:
            correct += 1
        detail.append({
            "index": i,
            "question": row.question,
            "options": row.options,
            "given": given,
            "correct_answer": row.answer,
            "is_correct": is_correct,
            # Returned for correct answers too, so a lucky guess still leaves the
            # learner with the reasoning.
            "explanation": row.explanation,
            "citations": row.citations or [],
        })

    pct = (correct / len(rows)) * 100.0
    return {
        "concept": concept,
        "score_pct": round(pct, 1),
        "passed": pct >= PASS_THRESHOLD_PCT,
        "total": len(rows),
        "correct": correct,
        "answers": detail,
    }


def record(
    db: Session,
    user: User,
    concept: str,
    question_ids: list[str],
    answers: list[int],
) -> QuizAttempt | None:
    """Score and persist. R8.5: the same ``concept`` value the Readiness Engine reads."""
    result = score(db, user, concept, question_ids, answers)
    if result is None:
        return None
    attempt = QuizAttempt(
        user_id=user.id,
        concept=concept,
        score_pct=result["score_pct"],
        passed=result["passed"],
        answers=result["answers"],
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt
