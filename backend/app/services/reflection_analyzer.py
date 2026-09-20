"""Evaluates the learner's own written reason for backing out of a trade.

This is the feature rules provably cannot do: rules cannot read free text at all.
When a learner cancels a trade and types *why*, the difference between these two
answers is the whole lesson —

    "holding because the company is still fine"        -> sound reasoning
    "holding because it'll definitely bounce tomorrow" -> a prediction, not a reason

Both produce the same score effect (backing out is good behaviour either way),
but only one is a habit worth keeping. Telling them apart requires understanding
language, so this is genuinely AI work rather than AI decoration.

The classification is deliberately advisory. It never changes whether the warning
counted as heeded — penalising someone for phrasing a good decision poorly would
discourage the exact behaviour the product wants.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.models import Reflection, User
from app.services import llm_gateway, retrieval
from app.services.llm_gateway import PromptSection

log = logging.getLogger(__name__)

# Anything shorter than this is not a reason, it's a shrug.
MIN_REASON_CHARS = 12

SOUND = "sound"
PARTLY_SOUND = "partly_sound"
PREDICTION_BASED = "prediction_based"
VALID_CLASSES = {SOUND, PARTLY_SOUND, PREDICTION_BASED}


_CLASS_GUIDANCE = """\
Classify the learner's reasoning into exactly one bucket:

- "sound": the reason refers to something that does not depend on guessing the
  future — company fundamentals unchanged, position size too large, plan says
  hold, horizon is long, they realised they were reacting emotionally.
- "prediction_based": the reason rests on a forecast of price or timing — it will
  bounce back, it's about to recover, prices always rise, it will hit a number.
  The decision may still be correct, but the justification is a guess.
- "partly_sound": contains a genuine reason AND a prediction, or is too vague to
  stand on its own.

Return ONLY valid JSON, no prose, no code fences:
{"classification": "sound|partly_sound|prediction_based",
 "concept": "the behavioural concept this demonstrates or contradicts",
 "response": "two or three sentences addressed to the learner as 'you'"}"""


def _fallback_classification(reason: str) -> tuple[str, str]:
    """Keyword heuristic for when no model is available.

    Deliberately crude and honest about it. It exists so the feature degrades to
    something useful rather than disappearing, not to replace the model.
    """
    lowered = reason.lower()

    prediction_markers = (
        "will bounce", "will recover", "will rise", "will go up", "will come back",
        "bounce back", "definitely", "guaranteed", "sure it will", "tomorrow it",
        "next week it", "always goes up", "will hit", "will reach", "gonna go up",
    )
    sound_markers = (
        "fundamental", "company is still", "business is still", "hasn't changed",
        "has not changed", "long term", "long-term", "my plan", "too much", "too big",
        "over-concentrat", "overconcentrat", "emotional", "panic", "diversif",
        "horizon", "not a good reason", "reacting",
    )

    has_prediction = any(m in lowered for m in prediction_markers)
    has_sound = any(m in lowered for m in sound_markers)

    if has_prediction and has_sound:
        return PARTLY_SOUND, (
            "There's a real reason in there, but part of it rests on predicting what "
            "the price will do next. Lead with the part that doesn't depend on a "
            "forecast — that's the reasoning worth keeping."
        )
    if has_prediction:
        return PREDICTION_BASED, (
            "Holding was very likely the right call, but the reason you gave is a "
            "prediction rather than a reason. Nobody knows what a price will do "
            "tomorrow. A stronger version: the business hasn't changed, only the price has."
        )
    if has_sound:
        return SOUND, (
            "That's sound reasoning — it doesn't depend on guessing where the price "
            "goes next. Deciding on the business and your plan rather than on the "
            "chart is exactly the habit that compounds."
        )
    return PARTLY_SOUND, (
        "Worth being more specific with yourself here. The strongest reasons don't "
        "depend on predicting the price: has the business changed, or has only the "
        "number on the screen changed?"
    )


def _parse(text: str) -> dict | None:
    """Pull the JSON object out of a model response.

    Models wrap JSON in prose or code fences often enough that being lenient
    about the envelope while strict about the contents is the pragmatic choice.
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
    classification = str(data.get("classification", "")).strip().lower()
    if classification not in VALID_CLASSES:
        return None
    response = str(data.get("response", "")).strip()
    if not response:
        return None
    return {
        "classification": classification,
        "concept": str(data.get("concept", "")).strip() or None,
        "response": response,
    }


def analyse(
    db: Session,
    user: User,
    reflection: Reflection,
    *,
    rule_ids: list[str] | None = None,
) -> dict:
    """Classify the learner's reason and persist the assessment.

    Never raises. An empty reason skips analysis entirely rather than asking a
    model to interpret whitespace.
    """
    reason = (reflection.reason or "").strip()
    if len(reason) < MIN_REASON_CHARS:
        return {"analysed": False, "reason": "no_text", "mode": "skipped"}

    # Ground the response in the concept the warning was about, so the reply cites
    # DolFin's own teaching rather than generic advice.
    query = f"{reason} {' '.join(rule_ids or [])}".strip()
    evidence = retrieval.retrieve(db, query, user_id=user.id, corpus="A", top_k=4)

    sections = [
        PromptSection(
            "Situation",
            f"The learner was about to {reflection.side} {reflection.quantity:g} of "
            f"{reflection.symbol} and cancelled after seeing a warning about "
            f"{', '.join(rule_ids or ['risk'])}.",
        ),
        PromptSection("Reference material", evidence.as_evidence() or "(none available)"),
        PromptSection("The learner's stated reason", reason, untrusted=True),
        PromptSection("Task", _CLASS_GUIDANCE),
    ]

    result = llm_gateway.generate(
        "reflection", sections, language=user.language, user_id=user.id
    )

    parsed = _parse(result.text) if result.ok else None
    if parsed:
        classification = parsed["classification"]
        response = parsed["response"]
        concept = parsed["concept"]
        mode = result.mode
        citations = evidence.citations()
    else:
        if result.ok:
            log.warning("Reflection response failed validation; using fallback.")
        classification, response = _fallback_classification(reason)
        concept = None
        mode = "offline"
        citations = evidence.citations()

    reflection.reasoning_class = classification
    reflection.ai_response = response
    reflection.ai_citations = citations
    reflection.ai_mode = mode
    db.commit()

    return {
        "analysed": True,
        "classification": classification,
        "response": response,
        "concept": concept,
        "citations": citations,
        "mode": mode,
    }
