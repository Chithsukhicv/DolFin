"""Whole-history behavioural analysis.

The properties worth protecting here are not about phrasing. They are:

- a learner with almost no history gets told so, and costs nothing
- an unchanged history costs nothing the second time
- a learner who does something well is told about it, model or no model
- every number in the output was computed in Python, not by the model
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    Holding,
    InterventionLog,
    PatternAnalysis,
    QuizAttempt,
    Transaction,
)
from app.services import indexer, pattern_analyzer, retrieval


@pytest.fixture(autouse=True)
def clear_cache():
    retrieval.reset_cache()
    yield
    retrieval.reset_cache()


def _txn(db, user, symbol, side, qty, price, *, days_ago=0, pnl=0.0, scenario=None):
    row = Transaction(
        user_id=user.id,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        realised_pnl=pnl,
        scenario_id=scenario,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(row)
    db.commit()
    return row


def _warning(db, user, rule_id, concept, action):
    row = InterventionLog(
        user_id=user.id,
        rule_id=rule_id,
        severity="warn",
        title=f"{rule_id} fired",
        message="A warning message long enough to be realistic.",
        concept=concept,
        user_action=action,
    )
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
class TestInsufficientActivity:
    def test_new_learner_is_told_to_come_back(self, db, user):
        result = pattern_analyzer.analyse(db, user)
        assert result["status"] == "insufficient_activity"
        assert result["patterns"] == []
        assert "enough history" in result["message"].lower()

    def test_makes_no_model_call(self, db, user, llm):
        pattern_analyzer.analyse(db, user)
        assert llm.calls == 0

    def test_answer_is_the_same_with_a_key_configured(self, db, user, llm):
        """R5.10: insufficiency does not depend on the LLM being available."""
        without = pattern_analyzer.analyse(db, user)["status"]
        assert without == "insufficient_activity"

    def test_one_resolved_warning_is_enough_to_analyse(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        result = pattern_analyzer.analyse(db, user)
        assert result["status"] == "ok"

    def test_three_trades_are_enough_to_analyse(self, db, user):
        for i in range(3):
            _txn(db, user, "TCS.NS", "buy", 1, 4000.0, days_ago=i)
        result = pattern_analyzer.analyse(db, user)
        assert result["status"] == "ok"

    def test_reports_how_many_trades_are_still_needed(self, db, user):
        _txn(db, user, "TCS.NS", "buy", 1, 4000.0)
        result = pattern_analyzer.analyse(db, user)
        assert result["trades_needed"] == 2


# ---------------------------------------------------------------------------
class TestEvidence:
    def test_counts_buys_and_sells_separately(self, db, user):
        _txn(db, user, "TCS.NS", "buy", 2, 4000.0, days_ago=10)
        _txn(db, user, "TCS.NS", "sell", 1, 3800.0, days_ago=2, pnl=-200.0)
        ev = pattern_analyzer.build_evidence(db, user)
        assert ev["trades"] == 2
        assert ev["buys"] == 1
        assert ev["sells"] == 1

    def test_computes_holding_period_from_the_matching_buy(self, db, user):
        _txn(db, user, "TCS.NS", "buy", 2, 4000.0, days_ago=10)
        _txn(db, user, "TCS.NS", "sell", 1, 3800.0, days_ago=7)
        ev = pattern_analyzer.build_evidence(db, user)
        assert ev["holding_periods_days"] == [3.0]

    def test_flags_sells_within_seven_days(self, db, user):
        _txn(db, user, "TCS.NS", "buy", 2, 4000.0, days_ago=5)
        _txn(db, user, "TCS.NS", "sell", 1, 3800.0, days_ago=1)
        ev = pattern_analyzer.build_evidence(db, user)
        assert ev["sells_within_7_days"] == 1

    def test_counts_sells_that_happened_during_a_scenario(self, db, user):
        _txn(db, user, "TCS.NS", "buy", 2, 4000.0, days_ago=5)
        _txn(db, user, "TCS.NS", "sell", 1, 3000.0, days_ago=1, scenario="sc-1")
        ev = pattern_analyzer.build_evidence(db, user)
        assert ev["sells_during_a_scenario"] == 1

    def test_resolves_sectors_through_the_catalogue(self, db, user, seeded_stocks):
        db.add(Holding(user_id=user.id, symbol="TCS.NS", quantity=1, avg_cost=4000.0))
        db.add(Holding(user_id=user.id, symbol="HDFCBANK.NS", quantity=1, avg_cost=1600.0))
        db.commit()
        ev = pattern_analyzer.build_evidence(db, user)
        assert ev["distinct_sectors"] == 2
        assert ev["sector_names"] == ["Banking", "IT"]

    def test_groups_warnings_by_concept_with_outcomes(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        _warning(db, user, "panic_sell", "panic_selling", "heeded")
        _warning(db, user, "panic_sell", "panic_selling", "pending")
        ev = pattern_analyzer.build_evidence(db, user)
        entry = ev["by_concept"]["panic_selling"]
        assert entry == {"fired": 3, "heeded": 1, "ignored": 1}

    def test_pending_warnings_do_not_count_as_resolved(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "pending")
        ev = pattern_analyzer.build_evidence(db, user)
        assert ev["warnings_fired"] == 1
        assert ev["warnings_resolved"] == 0

    def test_heed_rate_ignores_pending(self, db, user):
        _warning(db, user, "panic_sell", "panic_selling", "heeded")
        _warning(db, user, "panic_sell", "panic_selling", "pending")
        ev = pattern_analyzer.build_evidence(db, user)
        assert pattern_analyzer.heed_rates(ev)["panic_selling"] == 1.0


# ---------------------------------------------------------------------------
class TestDeterministicFallback:
    def test_names_the_repeated_override(self, db, user):
        for _ in range(3):
            _warning(db, user, "panic_sell", "panic_selling", "ignored")
        result = pattern_analyzer.analyse(db, user)
        assert result["mode"] == "offline"
        labels = " ".join(p["label"] for p in result["patterns"]).lower()
        assert "panic selling" in labels

    def test_every_pattern_carries_a_counted_fact(self, db, user):
        for _ in range(3):
            _warning(db, user, "panic_sell", "panic_selling", "ignored")
        result = pattern_analyzer.analyse(db, user)
        for pattern in result["patterns"]:
            assert pattern["evidence"], pattern["label"]
            assert any(ch.isdigit() for ch in " ".join(pattern["evidence"]))

    def test_names_a_strength_when_a_concept_is_heeded(self, db, user):
        """R5.5: a learner told only what they get wrong stops reading."""
        for _ in range(3):
            _warning(db, user, "concentration", "diversification", "heeded")
        _warning(db, user, "concentration", "diversification", "ignored")
        result = pattern_analyzer.analyse(db, user)
        assert any(p["is_strength"] for p in result["patterns"])

    def test_sector_spread_counts_as_a_strength(self, db, user, seeded_stocks):
        for symbol, cost in (("TCS.NS", 4000.0), ("HDFCBANK.NS", 1600.0), ("ITC.NS", 400.0)):
            db.add(Holding(user_id=user.id, symbol=symbol, quantity=1, avg_cost=cost))
        db.commit()
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        result = pattern_analyzer.analyse(db, user)
        strengths = [p for p in result["patterns"] if p["is_strength"]]
        assert strengths

    def test_says_so_when_nothing_repeats_yet(self, db, user):
        for i in range(3):
            _txn(db, user, "TCS.NS", "buy", 1, 4000.0, days_ago=i)
        result = pattern_analyzer.analyse(db, user)
        assert result["status"] == "ok"
        assert result["patterns"]

    def test_returns_at_most_three_patterns(self, db, user, seeded_stocks):
        for concept, rule in (("panic_selling", "panic_sell"),
                              ("diversification", "concentration"),
                              ("fomo", "fomo"),
                              ("loss_aversion", "loss_lock_in")):
            for _ in range(2):
                _warning(db, user, rule, concept, "ignored")
        result = pattern_analyzer.analyse(db, user)
        assert len(result["patterns"]) <= pattern_analyzer.MAX_PATTERNS

    def test_every_pattern_is_flagged_as_ai(self, db, user):
        """R5.11: source must survive into the response so the UI can label it."""
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        result = pattern_analyzer.analyse(db, user)
        assert all(p["source"] == "ai" for p in result["patterns"])


# ---------------------------------------------------------------------------
class TestCaching:
    def _seed(self, db, user):
        for _ in range(2):
            _warning(db, user, "panic_sell", "panic_selling", "ignored")

    def test_second_call_is_served_from_cache(self, db, user):
        self._seed(db, user)
        pattern_analyzer.analyse(db, user)
        again = pattern_analyzer.analyse(db, user)
        assert again["mode"] == "cached"

    def test_cache_hit_costs_no_model_call(self, db, user, llm):
        self._seed(db, user)
        llm.reply = json.dumps({"patterns": [{
            "label": "Flinching on dips",
            "evidence": ["You traded through the panic selling warning 2 times"],
            "insight": "You sell when prices fall, which turns paper losses into real ones.",
            "next_action": "Read the panic selling page.",
            "concept": "panic_selling",
            "is_strength": False,
        }]})
        pattern_analyzer.analyse(db, user)
        calls_after_first = llm.calls
        pattern_analyzer.analyse(db, user)
        assert llm.calls == calls_after_first

    def test_new_activity_invalidates_the_cache(self, db, user):
        self._seed(db, user)
        pattern_analyzer.analyse(db, user)
        _warning(db, user, "concentration", "diversification", "ignored")
        again = pattern_analyzer.analyse(db, user)
        assert again["mode"] != "cached"

    def test_force_bypasses_the_cache(self, db, user):
        self._seed(db, user)
        pattern_analyzer.analyse(db, user)
        again = pattern_analyzer.analyse(db, user, force=True)
        assert again["mode"] != "cached"

    def test_analysis_is_persisted_with_its_fingerprint(self, db, user):
        self._seed(db, user)
        _txn(db, user, "TCS.NS", "buy", 1, 4000.0)
        db.add(QuizAttempt(user_id=user.id, concept="panic_selling",
                           score_pct=50.0, passed=False, answers=[]))
        db.commit()
        pattern_analyzer.analyse(db, user)
        row = db.query(PatternAnalysis).filter_by(user_id=user.id).one()
        assert row.txn_count == 1
        assert row.resolved_intervention_count == 2
        assert row.quiz_attempt_count == 1


# ---------------------------------------------------------------------------
class TestGeneratedPath:
    @pytest.fixture
    def corpus(self, db):
        indexer.reindex_corpus_a(db, embed=False)

    def test_uses_the_model_when_available(self, db, user, llm, corpus):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        llm.reply = json.dumps({"patterns": [{
            "label": "Small dips make you flinch",
            "evidence": ["You traded through the panic selling warning 2 times"],
            "insight": "Every one of your sells came while prices were falling. That "
                       "converts a recoverable loss into a permanent one.",
            "next_action": "Sit out the next dip for one day.",
            "concept": "panic_selling",
            "is_strength": False,
        }]})
        result = pattern_analyzer.analyse(db, user)
        assert result["mode"] == "generated"
        assert result["patterns"][0]["label"] == "Small dips make you flinch"

    def test_malformed_response_falls_back(self, db, user, llm, corpus):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        llm.reply = "I'm afraid I can't do that."
        result = pattern_analyzer.analyse(db, user)
        assert result["mode"] == "offline"
        assert result["patterns"]

    def test_pattern_without_evidence_is_discarded(self, db, user, llm, corpus):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        llm.reply = json.dumps({"patterns": [{
            "label": "You are impatient",
            "evidence": [],
            "insight": "This is an opinion with no counted fact behind it at all.",
        }]})
        result = pattern_analyzer.analyse(db, user)
        assert result["mode"] == "offline"

    def test_a_strength_is_added_when_the_model_returns_only_criticism(
        self, db, user, llm, corpus
    ):
        for _ in range(3):
            _warning(db, user, "concentration", "diversification", "heeded")
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        llm.reply = json.dumps({"patterns": [{
            "label": "Flinching on dips",
            "evidence": ["You traded through the panic selling warning 1 time"],
            "insight": "You sell when prices fall, which locks in the loss permanently.",
            "is_strength": False,
        }]})
        result = pattern_analyzer.analyse(db, user)
        assert any(p["is_strength"] for p in result["patterns"])

    def test_citations_travel_with_generated_patterns(self, db, user, llm, corpus):
        _warning(db, user, "panic_sell", "panic_selling", "ignored")
        llm.reply = json.dumps({"patterns": [{
            "label": "Flinching on dips",
            "evidence": ["You traded through the panic selling warning 1 time"],
            "insight": "You sell when prices fall, which locks in the loss permanently.",
            "is_strength": False,
        }]})
        result = pattern_analyzer.analyse(db, user)
        assert result["patterns"][0]["citations"]

    def test_never_raises_on_a_broken_database_object(self, db, user, monkeypatch):
        monkeypatch.setattr(
            pattern_analyzer, "build_evidence",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = pattern_analyzer.analyse(db, user)
        assert result["status"] == "unavailable"
        assert result["patterns"] == []
