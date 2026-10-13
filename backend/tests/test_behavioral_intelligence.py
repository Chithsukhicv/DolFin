from datetime import date, datetime, timedelta, timezone

from app.models import InterventionLog, QuizAttempt, Reflection, Transaction, User
from app.services import behavioral_ml
from app.services.behavioral_evidence import _utc, build_behavioral_evidence
from app.services.evidence_aggregation import DimensionEstimate, aggregate_dimension, weighted_score


def test_practice_days_deduplicate_trade_bursts_and_merge_provenance(db, user):
    now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
    db.add_all([
        Transaction(user_id=user.id, symbol="TCS.NS", side="buy", quantity=1, price=100,
                    created_at=datetime(2026, 10, 12, 1)),
        Transaction(user_id=user.id, symbol="INFY.NS", side="buy", quantity=1, price=100,
                    created_at=datetime(2026, 10, 12, 2)),
        QuizAttempt(user_id=user.id, concept="risk", score_pct=40, passed=False, answers=[],
                    created_at=datetime(2026, 10, 12, 3)),
        Reflection(user_id=user.id, symbol="TCS.NS", side="sell", quantity=1,
                   triggering_rule_ids=[], reason="Reviewed the warning.",
                   created_at=datetime(2026, 10, 12, 1)),
        InterventionLog(user_id=user.id, rule_id="fomo", severity="warn", title="FOMO",
                        message="Pause", user_action="pending",
                        created_at=datetime(2026, 10, 10)),
    ])
    db.commit()

    evidence = build_behavioral_evidence(db, user, now=now)

    assert evidence["timezone"] == "UTC"
    assert evidence["practice_days"] == ["2026-10-12"]
    assert evidence["practice_day_sources"]["2026-10-12"] == ["quiz", "reflection", "trade"]
    assert evidence["qualifying_events"]["written_reflections"] == 1
    assert evidence["current_streak"] == 1
    assert evidence["rolling_30_day_practice_days"] == 1
    assert _utc(datetime(2026, 10, 11, 23, tzinfo=timezone(timedelta(hours=-2)))).date() == date(2026, 10, 12)


def test_only_completed_or_resolved_learning_events_qualify(db, user):
    db.add_all([
        QuizAttempt(user_id=user.id, concept="risk", score_pct=40, passed=False, answers=[]),
        Reflection(user_id=user.id, symbol="TCS.NS", side="sell", quantity=1,
                   triggering_rule_ids=[], reason="   "),
        InterventionLog(user_id=user.id, rule_id="fomo", severity="warn", title="FOMO",
                        message="Pause", user_action="pending"),
    ])
    db.commit()

    evidence = build_behavioral_evidence(db, user)

    assert evidence["practice_day_count"] == 1  # the completed quiz, even when failed
    assert evidence["qualifying_events"]["completed_quizzes"] == 1
    assert evidence["qualifying_events"]["written_reflections"] == 1


def test_intervention_preview_timestamp_is_not_used_as_a_practice_day(db, user):
    db.add(InterventionLog(
        user_id=user.id, rule_id="fomo", severity="warn", title="FOMO",
        message="Pause", user_action="heeded",
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
    ))
    db.commit()

    evidence = build_behavioral_evidence(db, user)

    assert evidence["practice_days"] == []


def test_practice_evidence_is_scoped_to_one_user(db, user):
    other = User(email="other@example.test", cash=100_000.0)
    db.add(other)
    db.flush()
    db.add(QuizAttempt(
        user_id=other.id, concept="risk", score_pct=100, passed=True,
        answers=[], created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    assert build_behavioral_evidence(db, user)["practice_days"] == []
    assert len(build_behavioral_evidence(db, other)["practice_days"]) == 1


def test_streak_breaks_without_erasing_longest(db, user):
    base = date.today()
    days = [base - timedelta(days=n) for n in (10, 9, 8, 4, 3, 2, 0)]
    for day in days:
        db.add(QuizAttempt(
            user_id=user.id, concept=f"risk-{day.isoformat()}", score_pct=100,
            passed=True, answers=[],
            created_at=datetime.combine(day, datetime.min.time()),
        ))
    db.commit()

    evidence = build_behavioral_evidence(db, user)

    assert evidence["current_streak"] == 1
    assert evidence["longest_streak"] == 3


def test_missing_ml_does_not_become_zero_and_blends_only_with_sufficient_sources():
    deterministic = DimensionEstimate(72, 15, 0.9, True, ("trade history",))
    fallback = aggregate_dimension(deterministic, None)
    assert fallback["score"] == 72
    assert fallback["source"] == "deterministic"
    assert fallback["fallback_reason"] == "ml_evidence_missing_or_invalid"

    insufficient_ml = DimensionEstimate(0, 2, 0.1, False, ("thin sample",))
    fallback = aggregate_dimension(deterministic, insufficient_ml)
    assert fallback["score"] == 72
    assert fallback["contributions"][1]["included"] is False

    ml = DimensionEstimate(52, 30, 0.95, True, ("longitudinal profile",))
    blended = aggregate_dimension(deterministic, ml, ml_weight=0.5)
    assert blended["score"] == 62
    assert blended["source"] == "blended"
    assert all(row["used_for_blending"] for row in blended["contributions"])

    excluded = aggregate_dimension(deterministic, ml, blend_enabled=False)
    assert excluded["score"] == 72
    assert excluded["source"] == "deterministic"
    assert excluded["contributions"][1]["included"] is False


def test_provisional_deterministic_estimate_is_visible_but_not_sufficient():
    estimate = DimensionEstimate(80, 1, 0.1, False, ("one practice day",))
    result = aggregate_dimension(estimate, None)
    assert result["score"] == 80
    assert result["sufficient"] is False
    assert result["fallback_reason"] == "deterministic_estimate_provisional"


def test_ml_only_evidence_cannot_make_a_dimension_assessable():
    ml = DimensionEstimate(5, 40, 0.95, True, ("anomaly profile",))
    result = aggregate_dimension(None, ml)
    assert result["score"] is None
    assert result["source"] == "none"
    assert result["sufficient"] is False
    assert result["contributions"][1]["included"] is False


def test_weighted_score_renormalizes_only_observed_dimensions():
    dimensions = {
        "a": {"score": 80},
        "b": {"score": None},
    }
    assert weighted_score(dimensions, {"a": 0.5, "b": 0.5}) == 80


def test_aggregator_rejects_invalid_estimates_without_turning_them_into_zero():
    invalid = DimensionEstimate(float("nan"), 100, 1, True)
    result = aggregate_dimension(invalid, None)
    assert result["score"] is None
    assert result["source"] == "none"
    assert result["contributions"][0]["reason"] == "invalid"


def test_anomaly_engine_cold_starts_and_labels_anomaly_as_non_scoring():
    cold = behavioral_ml.analyse_trade_anomalies({"trade_count": 4, "daily_trade_activity": []})
    assert cold["status"] == "insufficient_evidence"
    assert cold["affects_score"] is False

    daily = [
        {"date": f"2026-10-{day:02}", "trade_count": count, "gross_value": 1000}
        for day, count in enumerate([2, 2, 2, 2, 2, 12], start=1)
    ]
    result = behavioral_ml.analyse_trade_anomalies({
        "trade_count": sum(row["trade_count"] for row in daily),
        "daily_trade_activity": daily,
    })
    assert result["status"] == "analysed"
    assert result["affects_score"] is False
    assert result["findings"][0]["interpretation"] == "unusual_not_necessarily_risky"
