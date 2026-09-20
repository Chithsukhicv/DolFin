"""Context-aware coaching.

The point of this feature: the SAME fired rule must read differently depending on
the learner's history. A rule engine cannot make that distinction — it sees one
trade at a time — so this is genuinely AI work, and these tests pin the context
that gets handed to the model.
"""

from __future__ import annotations

from app.models import Goal, InterventionLog
from app.services import coach as coach_service
from app.services import portfolio as portfolio_service


def _warning(rule_id="concentration", concept="diversification", action="ignored"):
    return dict(rule_id=rule_id, concept=concept, user_action=action)


def _log(db, user, rule_id="concentration", concept="diversification", action="ignored"):
    db.add(InterventionLog(
        user_id=user.id, rule_id=rule_id, severity="warn",
        title="High concentration", message="Too much in one stock.",
        concept=concept, user_action=action, preview_id=f"p-{rule_id}-{action}",
    ))
    db.commit()


FIRED = [{
    "rule_id": "concentration",
    "severity": "critical",
    "title": "High concentration in a single stock",
    "message": "TCS would be 48% of your portfolio.",
    "concept": "diversification",
    "context": {},
}]


class TestLearnerContext:
    def test_counts_trades(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 2)
        portfolio_service.execute_buy(db, user, "INFY.NS", 2)
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["trades_total"] == 2

    def test_heed_rate_from_resolved_warnings_only(self, db, user, seeded_stocks):
        _log(db, user, action="heeded")
        _log(db, user, rule_id="fomo", action="ignored")
        _log(db, user, rule_id="short_hold", action="pending")

        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        # 1 heeded of 2 resolved; the pending row is evidence of nothing.
        assert ctx["warnings_resolved"] == 2
        assert ctx["heed_rate_overall"] == 0.5

    def test_no_heed_rate_before_anything_resolves(self, db, user, seeded_stocks):
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["heed_rate_overall"] is None

    def test_counts_repeat_offences_for_this_rule(self, db, user, seeded_stocks):
        for _ in range(3):
            db.add(InterventionLog(
                user_id=user.id, rule_id="concentration", severity="warn",
                title="t", message="m", concept="diversification",
                user_action="ignored", preview_id=None,
            ))
        db.commit()
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["times_ignored_these_rules"]["concentration"] == 3

    def test_heeded_warnings_are_not_counted_as_repeats(self, db, user, seeded_stocks):
        _log(db, user, action="heeded")
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["times_ignored_these_rules"] == {}

    def test_includes_goal_horizon(self, db, user, seeded_stocks):
        db.add(Goal(user_id=user.id, template_key="college", label="College",
                    target_amount=200_000.0, horizon_months=60))
        db.commit()
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["goal_horizon_months"] == 60

    def test_includes_risk_profile_and_persona(self, db, user, seeded_stocks):
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["risk_appetite"] == "low"
        assert ctx["persona"] == "teen"


class TestToneAdaptation:
    """The behavioural core: same rule, different framing."""

    def test_repeat_offender_gets_the_repetition_named(self, db, user, seeded_stocks):
        for _ in range(3):
            db.add(InterventionLog(
                user_id=user.id, rule_id="concentration", severity="warn",
                title="t", message="m", concept="diversification",
                user_action="ignored", preview_id=None,
            ))
        db.commit()
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        guidance = coach_service._tone_guidance(ctx)
        assert "more than once" in guidance.lower()

    def test_disciplined_learner_gets_credit_first(self, db, user, seeded_stocks):
        for i in range(9):
            db.add(InterventionLog(
                user_id=user.id, rule_id="fomo", severity="warn", title="t",
                message="m", concept="fomo", user_action="heeded", preview_id=f"h{i}",
            ))
        db.add(InterventionLog(
            user_id=user.id, rule_id="fomo", severity="warn", title="t",
            message="m", concept="fomo", user_action="ignored", preview_id="i1",
        ))
        db.commit()
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert ctx["heed_rate_overall"] == 0.9
        assert "track record" in coach_service._tone_guidance(ctx).lower()

    def test_beginner_gets_orientation_framing(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 1)
        ctx = coach_service.build_learner_context(db, user, ["concentration"])
        assert "first trades" in coach_service._tone_guidance(ctx).lower()

    def test_three_histories_produce_three_different_framings(self, db, user, seeded_stocks):
        """If these ever collapse to one string, the feature is doing nothing."""
        beginner = {"times_ignored_these_rules": {}, "heed_rate_overall": None, "trades_total": 1}
        repeat = {"times_ignored_these_rules": {"concentration": 3}, "heed_rate_overall": 0.1, "trades_total": 20}
        good = {"times_ignored_these_rules": {}, "heed_rate_overall": 0.9, "trades_total": 20}

        framings = {
            coach_service._tone_guidance(beginner),
            coach_service._tone_guidance(repeat),
            coach_service._tone_guidance(good),
        }
        assert len(framings) == 3


class TestPromptContents:
    def test_history_reaches_the_prompt(self, db, user, seeded_stocks, llm):
        for _ in range(3):
            db.add(InterventionLog(
                user_id=user.id, rule_id="concentration", severity="warn",
                title="t", message="m", concept="diversification",
                user_action="ignored", preview_id=None,
            ))
        db.commit()

        coach_service.coach_explain(
            FIRED, persona="teen", language="en",
            side="buy", symbol="TCS.NS", quantity=12, db=db, user=user,
        )
        prompt = llm.prompts[0]
        assert "track record" in prompt.lower()
        assert "3 time(s) before" in prompt

    def test_no_history_section_without_db(self, llm):
        coach_service.coach_explain(FIRED, persona="teen", language="en")
        assert "track record" not in llm.prompts[0].lower()

    def test_prompt_carries_the_proposed_trade(self, db, user, seeded_stocks, llm):
        coach_service.coach_explain(
            FIRED, side="sell", symbol="INFY.NS", quantity=5, db=db, user=user,
        )
        assert "sell 5 units of INFY.NS" in llm.prompts[0]

    def test_safety_constraints_are_inherited(self, db, user, seeded_stocks, llm):
        coach_service.coach_explain(FIRED, db=db, user=user)
        assert "Never predict a future price" in llm.prompts[0]

    def test_generated_message_is_returned(self, db, user, seeded_stocks, llm):
        llm.reply = "You've been here before with this one."
        out = coach_service.coach_explain(FIRED, db=db, user=user)
        assert out["mode"] == "generated"
        assert out["message"] == "You've been here before with this one."


class TestFallbacks:
    def test_offline_when_no_key(self, db, user, seeded_stocks):
        out = coach_service.coach_explain(FIRED, db=db, user=user)
        assert out["mode"] == "offline"
        assert "concentration" in out["message"].lower()

    def test_offline_message_still_names_the_repeat_pattern(self, db, user, seeded_stocks):
        """Even with no model, the repeat count is a plain Python fact."""
        for _ in range(3):
            db.add(InterventionLog(
                user_id=user.id, rule_id="concentration", severity="warn",
                title="t", message="m", concept="diversification",
                user_action="ignored", preview_id=None,
            ))
        db.commit()
        out = coach_service.coach_explain(FIRED, db=db, user=user)
        assert "3 times before" in out["message"]

    def test_screened_response_falls_back(self, db, user, seeded_stocks, llm):
        llm.reply = "You should sell TCS immediately."
        out = coach_service.coach_explain(FIRED, db=db, user=user)
        assert out["mode"] == "offline"
        assert "TCS immediately" not in out["message"]

    def test_clean_trade_gets_positive_confirmation(self):
        out = coach_service.coach_explain([], side="buy", symbol="ITC.NS", quantity=10)
        assert out["mode"] == "none"
        assert "considered trade" in out["message"]

    def test_clean_trade_message_in_hindi(self):
        out = coach_service.coach_explain([], side="buy", symbol="ITC.NS", quantity=10,
                                          language="hi")
        assert "warning nahi hai" in out["message"]
