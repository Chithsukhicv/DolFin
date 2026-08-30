"""LLM coach wrapper.

Two modes:
1. ``gemini``  : real Gemini API (when ``GEMINI_API_KEY`` is set).
2. ``offline`` : deterministic templated replies — used in dev and demos
                 when no key is available.

The intervention-engine output is the *source of truth*; the coach only
expands rule firings into a friendlier explanation.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable

from app.config import get_settings

log = logging.getLogger(__name__)

_PERSONA_TONE = {
    "woman": "Warm, supportive, treats the user as an intelligent peer building independence.",
    "teen": "Friendly, encouraging, plain-language, no jargon. Avoids being preachy.",
}

_LANG_HINT = {
    "en": "Respond in clear English.",
    "hi": "Hindi mein jawab dijiye, simple shabdon mein. (Respond in Hindi.)",
}


# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _gemini_client():
    """Build the Gemini model once and reuse it.

    Cached because this runs on every trade preview; re-running
    ``genai.configure`` per request is wasted work.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        return genai.GenerativeModel(settings.gemini_model)
    except Exception as e:  # pragma: no cover
        log.warning("Gemini init failed: %s", e)
        return None


def coach_explain(
    interventions: Iterable[dict],
    *,
    persona: str = "woman",
    language: str = "en",
    side: str | None = None,
    symbol: str | None = None,
    quantity: float | None = None,
) -> dict:
    """Turn a list of intervention dicts into a single friendly coach message."""
    items = list(interventions)
    if not items:
        return {
            "mode": "none",
            "message": _clean_trade_message(side, symbol, quantity, language),
        }

    client = _gemini_client()
    if client is None:
        return {"mode": "offline", "message": _offline_message(items)}

    prompt = _build_prompt(
        items, persona=persona, language=language,
        side=side, symbol=symbol, quantity=quantity,
    )
    try:
        response = client.generate_content(prompt)
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Empty response from Gemini")
        return {"mode": "gemini", "message": text}
    except Exception as e:  # pragma: no cover
        log.warning("Gemini call failed: %s — falling back to offline.", e)
        return {"mode": "offline", "message": _offline_message(items)}


def _clean_trade_message(
    side: str | None, symbol: str | None, quantity: float | None, language: str
) -> str:
    """Positive confirmation when no rule fires.

    A clean trade previously returned "No interventions fired", which reads as
    an error to a beginner. Naming it as good practice is the reinforcement
    half of the feedback loop.
    """
    if language == "hi":
        return (
            "Is trade par koi warning nahi hai. Aapka position size aur "
            "diversification theek lag rahe hain. Aage badhiye."
        )
    if side and symbol and quantity:
        verb = "buy" if side == "buy" else "sell"
        return (
            f"No warnings on this one. Your {verb} of {quantity:g} {symbol} sits within "
            f"sensible position-size and diversification limits, and it doesn't look like "
            f"a reaction to a price swing. This is what a considered trade looks like."
        )
    return (
        "No warnings on this one. Position size and diversification both look sensible. "
        "This is what a considered trade looks like."
    )


# ---------------------------------------------------------------------------
def _build_prompt(
    items: list[dict],
    *,
    persona: str,
    language: str,
    side: str | None = None,
    symbol: str | None = None,
    quantity: float | None = None,
) -> str:
    rules_block = "\n".join(
        f"- [{i['severity'].upper()}] {i['title']}: {i['message']}"
        f"  (concept={i.get('concept')}, context={i.get('context')})"
        for i in items
    )
    tone = _PERSONA_TONE.get(persona, _PERSONA_TONE["woman"])
    lang = _LANG_HINT.get(language, _LANG_HINT["en"])
    trade_line = ""
    if side and symbol and quantity:
        trade_line = f"The user is about to {side} {quantity:g} units of {symbol}.\n"
    return (
        "You are DolFin, an investment coach for first-time investors in India.\n"
        f"Tone: {tone}\n"
        f"{lang}\n\n"
        f"{trade_line}"
        "The rule engine fired these interventions before the user's trade:\n"
        f"{rules_block}\n\n"
        "Write a single short message (under 120 words) that:\n"
        "1. Acknowledges what the user is about to do.\n"
        "2. Explains the highest-severity concern in plain language.\n"
        "3. Teaches the underlying concept in one or two lines.\n"
        "4. Ends with a clear next-step suggestion (e.g. 'reduce size to X', 'wait a day').\n"
        "Never tell the user which specific stock to buy or sell, and never predict prices.\n"
        "Explain the principle so they can decide for themselves.\n"
        "Do not repeat the bullet list verbatim. Sound like a calm friend, not a compliance bot."
    )


def _offline_message(items: list[dict]) -> str:
    primary = items[0]
    extras = [f"Also: {i['title'].lower()}." for i in items[1:3]]
    extras_text = (" " + " ".join(extras)) if extras else ""
    return f"{primary['title']}. {primary['message']}{extras_text}"
