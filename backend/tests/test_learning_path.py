"""The adaptive learning path.

Two properties matter more than the ordering itself:

- ``done`` is computed from application data only, so progress can never regress
  because a model call failed
- with no gateway, the learner gets the original eight steps in the original
  order — a known-good sequence beats a half-personalised one
"""

from __future__ import annotations

import pytest

from app.models import Goal, Holding, InterventionLog, QuizAttempt, Transaction
from app.services import indexer, learning_path, retrieval

BASE_KEYS = [
    "goal", "learn_basics", "first_buy", "diversify",
    "face_crash", "hold_through", "prove_it", "graduate",
]


@pytest.fixture(autouse=True)
def clear_cache():
    retrieval.reset_cache()
    yield
    retrieval.reset_cache()


@pytest.fixture
def corpus(db):
    indexer.reindex_corpus_a(db, embed=False)
    return db


def _warning(db, user, rule_id, concept, action, count=1):
    for _ in range(count):
        db.add(InterventionLog(
            user_id=user.id, rule_id=rule_id, severity="warn",
            title=f"{rule_id} fired", message="A realistic warning message here.",
            concept=concept, user_action=action,
        ))
    db.commit()


# ---------------------------------------------------------------------------
class TestFixedFallback:
    def test_returns_the_original_eight_without_a_gateway(self, db, user):
        """R6.6."""
        path = learning_path.build_path(db, user)
        assert [s["key"] for s in path["steps"]] == BASE_KEYS
        assert path["adaptive"] is False

    def test_keeps_the_original_field_shape(self, db, user):
        """R6.4."""
        path = learning_path.build_path(db, user)
        for step in path["steps"]:
            for field in ("key", "title", "description", "done", "href", "action"):
                assert field in step, f"{step['key']} missing {field}"

    def test_reports_the_original_summary_fields(self, db, user):
        """R6.9."""
        path = learning_path.build_path(db, user)
        assert path["total"] == 8
        assert path["completed"] == 0
        assert path["percent"] == 0
        assert path["next_step"]["key"] == "goal"
        assert path["all_done"] is False

    def test_every_step_carries_a_rationale(self, db, user):
        """R6.3."""
        path = learning_path.build_path(db, user)
        assert all(s["rationale"].strip() for s in path["steps"])


# ---------------------------------------------------------------------------
class TestDeterministicProgress:
    def test_setting_a_goal_completes_the_first_step(self, db, user):
        db.add(Goal(user_id=user.id, template_key="emergency", label="Buffer",
                    target_amount=50_000.0, horizon_months=12))
        db.commit()
        path = learning_path.build_path(db, user)
        assert path["steps"][0]["done"] is True
        assert path["completed"] == 1

    def test_a_buy_completes_the_first_trade_step(self, db, user):
        db.add(Transaction(user_id=user.id, symbol="TCS.NS", side="buy",
                           quantity=1, price=4000.0))
        db.commit()
        keys = {s["key"]: s["done"] for s in learning_path.build_path(db, user)["steps"]}
        assert keys["first_buy"] is True

    def test_diversification_needs_both_count_and_spread(self, db, user, seeded_stocks):
        for symbol, cost in (("TCS.NS", 4000.0), ("INFY.NS", 1500.0),
                             ("HDFCBANK.NS", 1600.0), ("ITC.NS", 400.0)):
            db.add(Holding(user_id=user.id, symbol=symbol, quantity=1, avg_cost=cost))
        db.commit()
        step = next(s for s in learning_path.build_path(db, user)["steps"]
                    if s["key"] == "diversify")
        assert step["done"] is True

    def test_two_sectors_is_not_enough(self, db, user, seeded_stocks):
        for symbol, cost in (("TCS.NS", 4000.0), ("INFY.NS", 1500.0)):
            db.add(Holding(user_id=user.id, symbol=symbol, quantity=1, avg_cost=cost))
        db.commit()
        step = next(s for s in learning_path.build_path(db, user)["steps"]
                    if s["key"] == "diversify")
        assert step["done"] is False

    def test_holding_through_a_downturn_requires_a_heeded_panic_warning(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "heeded")
        step = next(s for s in learning_path.build_path(db, user)["steps"]
                    if s["key"] == "hold_through")
        assert step["done"] is True

    def test_ignoring_the_panic_warning_does_not_complete_it(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        step = next(s for s in learning_path.build_path(db, user)["steps"]
                    if s["key"] == "hold_through")
        assert step["done"] is False

    def test_progress_is_identical_with_a_gateway_available(self, db, user, llm, corpus):
        """R6.5: ``done`` never depends on the model."""
        db.add(Goal(user_id=user.id, template_key="emergency", label="Buffer",
                    target_amount=50_000.0, horizon_months=12))
        db.commit()
        offline = {s["key"]: s["done"]
                   for s in learning_path._base_steps(db, user)}
        adaptive = {s["key"]: s["done"]
                    for s in learning_path.build_path(db, user)["steps"]
                    if s["key"] in offline}
        assert adaptive == offline


# ---------------------------------------------------------------------------
class TestWeaknessMeasurement:
    def test_counts_ignored_warnings_per_concept(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=3)
        weak = learning_path.measure_weaknesses(db, user)
        assert weak["panic_selling"]["ignored"] == 3

    def test_pending_warnings_are_not_counted_against_the_learner(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "pending", count=3)
        weak = learning_path.measure_weaknesses(db, user)
        assert weak["panic_selling"]["ignored"] == 0
        assert weak["panic_selling"]["score"] == 0

    def test_counts_failed_quizzes(self, db, user):
        db.add(QuizAttempt(user_id=user.id, concept="fomo", score_pct=33.0,
                           passed=False, answers=[]))
        db.commit()
        weak = learning_path.measure_weaknesses(db, user)
        assert weak["fomo"]["failed_quizzes"] == 1

    def test_an_ignored_warning_outweighs_a_failed_quiz(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        db.add(QuizAttempt(user_id=user.id, concept="fomo", score_pct=33.0,
                           passed=False, answers=[]))
        db.commit()
        weak = learning_path.measure_weaknesses(db, user)
        assert weak["panic_selling"]["score"] > weak["fomo"]["score"]

    def test_a_passed_quiz_is_recorded_without_erasing_the_override(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=2)
        db.add(QuizAttempt(user_id=user.id, concept="panic_selling", score_pct=100.0,
                           passed=True, answers=[]))
        db.commit()
        weak = learning_path.measure_weaknesses(db, user)
        assert weak["panic_selling"]["passed_quiz"] is True
        assert weak["panic_selling"]["score"] > 0

    def test_heeded_warnings_do_not_create_a_weakness(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "heeded", count=4)
        weak = learning_path.measure_weaknesses(db, user)
        assert weak["panic_selling"]["score"] == 0


# ---------------------------------------------------------------------------
class TestAdaptiveOrdering:
    def test_adds_a_remedial_step_for_the_ignored_concept(self, db, user, llm, corpus):
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=3)
        path = learning_path.build_path(db, user)
        assert path["adaptive"] is True
        assert "fix:panic_selling" in [s["key"] for s in path["steps"]]

    def test_the_weakest_concept_becomes_the_next_step(self, db, user, llm, corpus):
        """R6.2."""
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=4)
        _warning(db, user, "concentration", "diversification", "ignored", count=1)
        path = learning_path.build_path(db, user)
        assert path["next_step"]["concept"] == "panic_selling"

    def test_remedial_step_names_the_evidence(self, db, user, llm, corpus):
        """R6.3."""
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=3)
        path = learning_path.build_path(db, user)
        step = next(s for s in path["steps"] if s["key"] == "fix:panic_selling")
        assert "3 time(s)" in step["rationale"]

    def test_original_order_survives_when_there_is_no_evidence(self, db, user, llm, corpus):
        path = learning_path.build_path(db, user)
        assert [s["key"] for s in path["steps"]] == BASE_KEYS

    def test_completed_steps_move_below_outstanding_ones(self, db, user, llm, corpus):
        db.add(Goal(user_id=user.id, template_key="emergency", label="Buffer",
                    target_amount=50_000.0, horizon_months=12))
        db.commit()
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=2)
        path = learning_path.build_path(db, user)
        assert path["next_step"]["done"] is False

    def test_remedial_step_links_to_the_concept_page(self, db, user, llm, corpus):
        _warning(db, user, "fomo", "fomo", "ignored", count=2)
        path = learning_path.build_path(db, user)
        step = next(s for s in path["steps"] if s["key"] == "fix:fomo")
        assert step["href"] == "/learn/fomo"

    def test_remedial_step_completes_once_the_quiz_is_passed_and_nothing_ignored(
        self, db, user, llm, corpus
    ):
        db.add(QuizAttempt(user_id=user.id, concept="fomo", score_pct=33.0,
                           passed=False, answers=[]))
        db.add(QuizAttempt(user_id=user.id, concept="fomo", score_pct=100.0,
                           passed=True, answers=[]))
        db.commit()
        path = learning_path.build_path(db, user)
        step = next(s for s in path["steps"] if s["key"] == "fix:fomo")
        assert step["done"] is True

    def test_only_corpus_a_concepts_get_a_remedial_step(self, db, user, llm, corpus):
        """R6.8: never point a learner at material that does not exist."""
        _warning(db, user, "mystery_rule", "not_in_corpus", "ignored", count=5)
        path = learning_path.build_path(db, user)
        assert "fix:not_in_corpus" not in [s["key"] for s in path["steps"]]

    def test_summary_fields_account_for_the_added_steps(self, db, user, llm, corpus):
        _warning(db, user, "panic_sell", "panic_selling", "ignored", count=2)
        path = learning_path.build_path(db, user)
        assert path["total"] == len(path["steps"])
        assert path["percent"] == round(path["completed"] / path["total"] * 100)


# ---------------------------------------------------------------------------
class TestDegradedMode:
    def test_a_computation_failure_still_returns_eight_steps(self, db, user, monkeypatch):
        """R6.7."""
        monkeypatch.setattr(
            learning_path, "_base_steps",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        path = learning_path.build_path(db, user)
        assert [s["key"] for s in path["steps"]] == BASE_KEYS
        assert path["degraded"] is True

    def test_degraded_mode_never_invents_progress(self, db, user, monkeypatch):
        monkeypatch.setattr(
            learning_path, "_base_steps",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        path = learning_path.build_path(db, user)
        assert all(s["done"] is False for s in path["steps"])
        assert path["next_step"]["key"] == "goal"
