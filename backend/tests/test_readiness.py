"""Readiness Score behaviour.

The bug these tests exist to prevent: a learner who bought two stocks and sold
one scored 47/100, which reads as halfway to being ready for real money. The
score must reflect *demonstrated habits*, so thin evidence has to produce a low
number even when nothing has gone wrong yet.
"""

from __future__ import annotations

import pytest

from app.models import Goal, QuizAttempt
from app.services import portfolio as portfolio_service
from app.services import readiness as readiness_service


def _goal(db, user, horizon=36):
    db.add(Goal(
        user_id=user.id, template_key="college_fund", label="College fund",
        target_amount=200_000.0, horizon_months=horizon,
    ))
    db.commit()


class TestBeginnerScores:
    def test_brand_new_user_scores_zero(self, db, user, seeded_stocks):
        result = readiness_service.compute_readiness(db, user)
        assert result["score"] == 0.0
        assert result["is_active"] is False
        assert result["graduated"] is False

    def test_two_buys_one_sell_stays_low(self, db, user, seeded_stocks):
        """The exact scenario that used to score 47."""
        _goal(db, user)
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        portfolio_service.execute_buy(db, user, "INFY.NS", 5)
        portfolio_service.execute_sell(db, user, "INFY.NS", 5)

        result = readiness_service.compute_readiness(db, user)
        assert result["score"] < 30, (
            f"3 trades and 1 concentrated holding scored {result['score']}, "
            "which overstates readiness"
        )
        assert result["provisional"] is True
        assert result["graduated"] is False

    def test_provisional_flag_reports_what_is_missing(self, db, user, seeded_stocks):
        _goal(db, user)
        portfolio_service.execute_buy(db, user, "TCS.NS", 2)
        result = readiness_service.compute_readiness(db, user)

        assert result["confidence"] < 1.0
        assert result["evidence_needed"]["trades"] > 0
        assert result["evidence_needed"]["holdings"] > 0

    def test_single_holding_gets_no_diversification_credit(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 10)
        result = readiness_service.compute_readiness(db, user)
        assert result["breakdown"]["diversification"] < 15


class TestGraduationIsReachable:
    def test_disciplined_diversified_user_can_graduate(self, db, user, seeded_stocks):
        """The ramp must not make 80+ unreachable for genuinely good behaviour."""
        _goal(db, user)
        # Eight distinct holdings across six sectors satisfies FULL_CONFIDENCE_HOLDINGS=8.
        for symbol, qty in [
            ("TCS.NS", 4), ("INFY.NS", 10), ("HDFCBANK.NS", 9),
            ("SUNPHARMA.NS", 12), ("RELIANCE.NS", 11), ("ITC.NS", 20),
            ("TATASTEEL.NS", 5), ("NIFTYBEES.NS", 8),
        ]:
            portfolio_service.execute_buy(db, user, symbol, qty)
        # Enough trades to reach full confidence on the trade axis.
        for _ in range(2):
            portfolio_service.execute_buy(db, user, "ITC.NS", 1)
            portfolio_service.execute_buy(db, user, "INFY.NS", 1)
        for concept in ("diversification", "panic_selling", "long_term_thinking"):
            db.add(QuizAttempt(
                user_id=user.id, concept=concept, score_pct=100.0,
                passed=True, answers=[],
            ))
        db.commit()

        result = readiness_service.compute_readiness(db, user)
        assert result["confidence"] == 1.0
        assert result["score"] >= 80, f"good behaviour only scored {result['score']}"
        assert result["graduated"] is True


class TestQuizzesCount:
    def test_passing_quizzes_raises_discipline(self, db, user, seeded_stocks):
        """The UI promises a discipline boost; it has to be real."""
        portfolio_service.execute_buy(db, user, "TCS.NS", 2)
        before = readiness_service.compute_readiness(db, user)["breakdown"]["discipline"]

        db.add(QuizAttempt(
            user_id=user.id, concept="diversification", score_pct=100.0,
            passed=True, answers=[],
        ))
        db.commit()

        after = readiness_service.compute_readiness(db, user)["breakdown"]["discipline"]
        assert after > before

    def test_failed_quizzes_give_nothing(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 2)
        before = readiness_service.compute_readiness(db, user)["breakdown"]["discipline"]

        db.add(QuizAttempt(
            user_id=user.id, concept="diversification", score_pct=33.0,
            passed=False, answers=[],
        ))
        db.commit()

        after = readiness_service.compute_readiness(db, user)["breakdown"]["discipline"]
        assert after == before

    def test_retaking_same_quiz_does_not_stack(self, db, user, seeded_stocks):
        """Otherwise a learner could grind one quiz instead of diversifying."""
        portfolio_service.execute_buy(db, user, "TCS.NS", 2)
        for _ in range(5):
            db.add(QuizAttempt(
                user_id=user.id, concept="diversification", score_pct=100.0,
                passed=True, answers=[],
            ))
        db.commit()
        once = readiness_service._quiz_bonus(db, user)
        assert once == readiness_service.QUIZ_PASS_BONUS

    def test_quiz_bonus_is_capped(self, db, user, seeded_stocks):
        for concept in ("diversification", "panic_selling", "fomo", "sip",
                        "market_cycles", "cash_management", "index_funds"):
            db.add(QuizAttempt(
                user_id=user.id, concept=concept, score_pct=100.0,
                passed=True, answers=[],
            ))
        db.commit()
        assert readiness_service._quiz_bonus(db, user) == readiness_service.QUIZ_BONUS_CAP


class TestScoreBounds:
    @pytest.mark.parametrize("symbol,qty", [("TCS.NS", 1), ("ITC.NS", 100)])
    def test_score_always_within_range(self, db, user, seeded_stocks, symbol, qty):
        portfolio_service.execute_buy(db, user, symbol, qty)
        result = readiness_service.compute_readiness(db, user)
        assert 0.0 <= result["score"] <= 100.0
        for name, value in result["breakdown"].items():
            assert 0.0 <= value <= 100.0, f"{name} out of range: {value}"
