"""Quizzes, the concept library and the guided path.

These are content-integrity tests. Educational content fails quietly: a quiz
with a broken answer index or a concept pointing at a nonexistent quiz still
renders fine and simply teaches the wrong thing.
"""

from __future__ import annotations

import pytest

from app.data import concepts_seed, quizzes_seed
from app.data.stocks_seed import SEED_STOCKS
from app.services import learning_path as path_service
from app.services import portfolio as portfolio_service
from app.services import quizzes as quiz_service


class TestQuizIntegrity:
    @pytest.mark.parametrize("concept", quizzes_seed.concept_keys())
    def test_every_bank_has_enough_questions(self, concept):
        """With one question the only scores are 0% and 100%, making the 80%
        pass mark meaningless."""
        assert len(quizzes_seed.QUIZZES[concept]) >= 2

    @pytest.mark.parametrize("concept", quizzes_seed.concept_keys())
    def test_answer_indices_are_valid(self, concept):
        for i, q in enumerate(quizzes_seed.QUIZZES[concept]):
            assert 0 <= q["answer"] < len(q["options"]), f"{concept}[{i}] answer out of range"

    @pytest.mark.parametrize("concept", quizzes_seed.concept_keys())
    def test_every_question_explains_itself(self, concept):
        """A wrong answer reporting only 'correct option: 2' teaches nothing."""
        for i, q in enumerate(quizzes_seed.QUIZZES[concept]):
            assert q.get("explanation"), f"{concept}[{i}] has no explanation"
            assert len(q["explanation"]) > 40

    @pytest.mark.parametrize("concept", quizzes_seed.concept_keys())
    def test_options_are_distinct(self, concept):
        for i, q in enumerate(quizzes_seed.QUIZZES[concept]):
            assert len(set(q["options"])) == len(q["options"]), f"{concept}[{i}] repeats an option"


class TestQuizScoring:
    def test_all_correct_passes(self, db):
        answers = [q["answer"] for q in quizzes_seed.QUIZZES["diversification"]]
        result = quiz_service.score_attempt("diversification", answers)
        assert result["score_pct"] == 100.0
        assert result["passed"] is True

    def test_all_wrong_fails(self, db):
        raw = quizzes_seed.QUIZZES["diversification"]
        answers = [(q["answer"] + 1) % len(q["options"]) for q in raw]
        result = quiz_service.score_attempt("diversification", answers)
        assert result["score_pct"] == 0.0
        assert result["passed"] is False

    def test_two_of_three_falls_short_of_the_bar(self, db):
        raw = quizzes_seed.QUIZZES["panic_selling"]
        answers = [q["answer"] for q in raw]
        answers[0] = (answers[0] + 1) % len(raw[0]["options"])
        result = quiz_service.score_attempt("panic_selling", answers)
        assert result["score_pct"] == pytest.approx(66.7, abs=0.1)
        assert result["passed"] is False

    def test_explanations_returned_for_every_question(self, db):
        answers = [q["answer"] for q in quizzes_seed.QUIZZES["sip"]]
        result = quiz_service.score_attempt("sip", answers)
        assert all(a["explanation"] for a in result["answers"])

    def test_missing_answers_are_counted_wrong_not_crashed(self, db):
        result = quiz_service.score_attempt("diversification", [])
        assert result["passed"] is False
        assert result["correct"] == 0

    def test_questions_hide_the_answer_key(self):
        for item in quiz_service.get_quiz("diversification"):
            assert "answer" not in item

    def test_unknown_concept_is_empty(self):
        assert quiz_service.get_quiz("not_a_concept") == []


class TestConceptLibrary:
    def test_every_concept_has_teaching_content(self):
        for c in concepts_seed.CONCEPTS:
            assert c["title"] and c["one_liner"]
            assert len(c["body"]) >= 2, f"{c['key']} is too thin to teach from"
            assert c["takeaways"], f"{c['key']} has no takeaways"
            assert c["misconception"]["myth"] and c["misconception"]["reality"]

    def test_concept_quiz_links_resolve(self):
        """A concept advertising a quiz that doesn't exist is a dead end."""
        for c in concepts_seed.CONCEPTS:
            quiz = c.get("quiz")
            if quiz:
                assert quizzes_seed.quizzes_for_concept(quiz), f"{c['key']} → missing quiz {quiz}"

    def test_every_quiz_is_reachable_from_a_concept(self):
        """Otherwise a bank is only findable by typing the URL."""
        linked = {c.get("quiz") for c in concepts_seed.CONCEPTS}
        for concept in quizzes_seed.concept_keys():
            assert concept in linked, f"quiz '{concept}' has no concept page"

    def test_rule_concepts_are_all_documented(self):
        """Every rule that fires must have somewhere to send the learner."""
        from app.services import interventions

        rule_concepts = {
            "diversification", "risk_appetite", "fomo", "cash_management",
            "market_cycles", "panic_selling", "loss_aversion",
            "long_term_thinking", "index_funds",
        }
        documented = {c["key"] for c in concepts_seed.CONCEPTS}
        assert rule_concepts <= documented, f"undocumented: {rule_concepts - documented}"

    def test_lookup_helpers(self):
        assert concepts_seed.get_concept("diversification")["title"] == "Diversification"
        assert concepts_seed.get_concept("nope") is None
        assert concepts_seed.concept_for_rule("panic_sell")["key"] == "panic_selling"

    def test_summary_view_omits_the_body(self):
        for c in concepts_seed.all_concepts(summary=True):
            assert "body" not in c

    def test_glossary_definitions_are_short_and_present(self):
        for entry in concepts_seed.glossary_terms():
            assert entry["definition"]
            assert len(entry["definition"]) < 400, f"{entry['term']} is too long for a tooltip"


class TestCatalogueSupportsTheCurriculum:
    def test_index_funds_exist_so_sip_is_practisable(self):
        """SIP and index investing are taught; they must also be doable."""
        etfs = [s for s in SEED_STOCKS if s["sector"] == "Index Fund"]
        assert len(etfs) >= 3

    def test_enough_sectors_for_the_diversification_target(self):
        sectors = {s["sector"] for s in SEED_STOCKS}
        assert len(sectors) >= 5

    def test_high_risk_stocks_exist_for_the_mismatch_rule(self):
        assert any(s["risk_level"] == "high" for s in SEED_STOCKS)

    def test_symbols_are_unique(self):
        symbols = [s["symbol"] for s in SEED_STOCKS]
        assert len(symbols) == len(set(symbols))


class TestLearningPath:
    def test_new_user_gets_a_next_step(self, db, user, seeded_stocks):
        path = path_service.build_path(db, user)
        assert path["completed"] < path["total"]
        assert path["next_step"] is not None
        assert path["next_step"]["href"]
        assert path["next_step"]["action"]

    def test_first_buy_advances_the_path(self, db, user, seeded_stocks):
        before = path_service.build_path(db, user)["completed"]
        portfolio_service.execute_buy(db, user, "TCS.NS", 2)
        after = path_service.build_path(db, user)["completed"]
        assert after > before

    def test_steps_are_ordered_so_the_crash_comes_after_investing(self, db, user, seeded_stocks):
        """A crash is not instructive with nothing invested to watch fall."""
        keys = [s["key"] for s in path_service.build_path(db, user)["steps"]]
        assert keys.index("first_buy") < keys.index("face_crash")
        assert keys.index("face_crash") < keys.index("hold_through")
        assert keys[-1] == "graduate"

    def test_progress_percentage_is_sane(self, db, user, seeded_stocks):
        path = path_service.build_path(db, user)
        assert 0 <= path["percent"] <= 100
