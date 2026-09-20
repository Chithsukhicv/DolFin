"""Bilingual AI output, and what happens when the model ignores the request.

The interesting case is not "Hindi works". It is that a model asked for Hindi
frequently answers in English anyway. Trusting the instruction would mean shipping
English text labelled as Hindi, which is worse than shipping English text that
says so — a learner who asked for Hindi and got English at least understands what
happened.

So the gateway checks the script of what came back and reports the language it
actually got, separately from the one that was requested.
"""

from __future__ import annotations

import json

import pytest

from app.models import Reflection
from app.services import chatbot, coach, indexer, llm_gateway, reflection_analyzer, retrieval
from app.services.llm_gateway import PromptSection

HINDI = (
    "Aapka portfolio ek hi company mein bahut zyada hai. "
    "यह जोखिम भरा है क्योंकि एक कंपनी गिरने पर पूरा नुकसान होगा। "
    "थोड़ा और फैलाइए।"
)
ENGLISH = "Your portfolio is concentrated in one company, which is risky."


@pytest.fixture(autouse=True)
def clear_cache():
    retrieval.reset_cache()
    yield
    retrieval.reset_cache()


@pytest.fixture
def corpus(db):
    indexer.reindex_corpus_a(db, embed=False)
    return db


@pytest.fixture
def hindi_user(db, user):
    user.language = "hi"
    db.commit()
    return user


def _sections():
    return [PromptSection("Task", "Explain why concentration is risky.")]


# ---------------------------------------------------------------------------
class TestScriptDetection:
    @pytest.mark.parametrize("text", [
        "यह जोखिम भरा है क्योंकि एक कंपनी गिरने पर नुकसान होगा।",
        HINDI,
        "आपका P/E ratio 25 है, जो थोड़ा ऊँचा है।",
    ])
    def test_recognises_hindi(self, text):
        assert llm_gateway.looks_hindi(text)

    @pytest.mark.parametrize("text", [
        ENGLISH,
        "Diversification means spreading money across companies.",
        "",
        "12345 %$#",
    ])
    def test_rejects_non_hindi(self, text):
        assert not llm_gateway.looks_hindi(text)

    def test_tolerates_latin_finance_terms_inside_hindi(self):
        """Real Hindi finance writing is full of Latin-script jargon."""
        mixed = (
            "आपका SIP हर month चलता है और NSE पर listed index fund "
            "खरीदता है, जो अच्छा तरीका है।"
        )
        assert llm_gateway.looks_hindi(mixed)

    def test_a_stray_hindi_word_does_not_make_english_hindi(self):
        mostly_english = (
            "Diversification means spreading your money across many different "
            "companies and sectors so that one bad outcome cannot dominate the "
            "result. This is the single most important habit for a beginner. नमस्ते"
        )
        assert not llm_gateway.looks_hindi(mostly_english)


# ---------------------------------------------------------------------------
class TestGatewayLanguagePolicy:
    def test_hindi_response_is_reported_as_hindi(self, llm):
        llm.reply = HINDI
        result = llm_gateway.generate("coach", _sections(), language="hi")
        assert result.ok
        assert result.language == "hi"
        assert result.language_fallback is False

    def test_english_response_to_a_hindi_request_is_reported_as_english(self, llm):
        """R19.7: return it as the English output rather than mislabelling it."""
        llm.reply = ENGLISH
        result = llm_gateway.generate("coach", _sections(), language="hi")
        assert result.ok
        assert result.text == ENGLISH
        assert result.language == "en"
        assert result.language_fallback is True

    def test_a_failed_hindi_call_is_retried_in_english(self, llm, monkeypatch):
        """One English attempt beats handing back a template."""
        prompts: list[str] = []

        def reply(prompt: str, *, timeout: float) -> str:
            prompts.append(prompt)
            # The Hindi prompt is identifiable by its language hint.
            if "Respond in Hindi" in prompt:
                raise RuntimeError("model refused the Hindi request")
            return ENGLISH

        monkeypatch.setattr(llm_gateway, "_call_model", reply)

        result = llm_gateway.generate("coach", _sections(), language="hi")
        assert result.ok
        assert result.text == ENGLISH
        assert result.language == "en"
        assert result.language_fallback is True
        assert any("Respond in Hindi" in p for p in prompts), "never tried Hindi first"
        assert any("plain English" in p for p in prompts), "never retried in English"

    def test_a_total_failure_still_reports_a_language_fallback(self, llm):
        llm.error = RuntimeError("down")
        result = llm_gateway.generate("coach", _sections(), language="hi")
        assert result.ok is False
        assert result.language_fallback is True

    def test_an_english_request_is_left_alone(self, llm):
        llm.reply = ENGLISH
        result = llm_gateway.generate("coach", _sections(), language="en")
        assert result.language == "en"
        assert result.language_fallback is False

    def test_an_unsupported_language_falls_back_to_english(self, llm):
        """R19.6."""
        llm.reply = ENGLISH
        result = llm_gateway.generate("coach", _sections(), language="ta")
        assert result.ok
        assert result.language == "en"
        # The prompt should carry the English hint, not a Tamil one.
        assert "plain English" in llm.prompts[0]

    def test_the_hindi_prompt_asks_for_hindi(self, llm):
        llm.reply = HINDI
        llm_gateway.generate("coach", _sections(), language="hi")
        assert "Respond in Hindi" in llm.prompts[0]

    def test_hindi_and_english_are_cached_separately(self, llm):
        """A cache keyed without language would serve the wrong one."""
        llm.reply = HINDI
        llm_gateway.generate("coach", _sections(), language="hi")
        before = llm.calls
        llm_gateway.generate("coach", _sections(), language="en")
        assert llm.calls > before


# ---------------------------------------------------------------------------
class TestFeaturesRespectLanguage:
    def test_coach_requests_the_learners_language(self, db, hindi_user, llm):
        llm.reply = HINDI
        coach.coach_explain(
            [{
                "rule_id": "concentration", "severity": "warn",
                "title": "Too concentrated", "message": "One name is a large share.",
                "concept": "diversification",
            }],
            persona=hindi_user.persona,
            language=hindi_user.language,
            db=db,
            user=hindi_user,
        )
        assert "Respond in Hindi" in llm.prompts[0]

    def test_chatbot_requests_the_learners_language(self, db, hindi_user, corpus, llm):
        llm.reply = HINDI
        chatbot.ask(db, hindi_user, "panic selling kya hai")
        assert "Respond in Hindi" in llm.prompts[0]

    def test_reflection_analyzer_requests_the_learners_language(
        self, db, hindi_user, corpus, llm
    ):
        llm.reply = json.dumps({
            "classification": "prediction_based",
            "concept": "panic_selling",
            "response": "यह एक अनुमान है, कारण नहीं। कंपनी बदली है या सिर्फ कीमत?",
        })
        ref = Reflection(
            user_id=hindi_user.id, symbol="TCS.NS", side="sell", quantity=1,
            triggering_rule_ids=["panic_sell"],
            reason="kal wapas bounce karega isliye hold kar raha hoon",
        )
        db.add(ref)
        db.commit()
        result = reflection_analyzer.analyse(db, hindi_user, ref, rule_ids=["panic_sell"])
        assert "Respond in Hindi" in llm.prompts[0]
        assert result["classification"] == "prediction_based"

    def test_retrieval_stays_on_the_english_corpus(self, db, hindi_user, corpus, llm):
        """R19.4: Corpus A is English regardless of output language."""
        llm.reply = HINDI
        result = chatbot.ask(db, hindi_user, "diversification kya hai")
        titles = [c["source_title"] for c in result["citations"]]
        assert titles
        # Source titles are rendered in the language of the indexed material (R19.5).
        assert any(any(ch.isascii() and ch.isalpha() for ch in t) for t in titles)

    def test_hindi_offline_fallback_is_in_hindi(self, db, hindi_user, corpus):
        """No gateway at all — the deterministic path must still be bilingual."""
        result = chatbot.ask(db, hindi_user, "panic selling kya hai")
        assert result["mode"] == "offline"
        assert "padhiye" in result["answer"].lower()

    def test_hindi_no_material_message_is_in_hindi(self, db, hindi_user):
        result = chatbot.ask(db, hindi_user, "1994 football world cup kaun jeeta")
        assert result["grounded"] is False
        assert "andaaza" in result["answer"].lower()
