"""Market scenario simulator: the multiplier curve and lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services import portfolio as portfolio_service
from app.services import scenarios as svc


def _at(scenario, days):
    """Helper: evaluate the curve N days after the scenario started."""
    start = scenario.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return svc.current_multiplier(scenario, now=start + timedelta(days=days))


class TestCrashCurve:
    def test_starts_at_full_value(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        assert _at(s, 0) == pytest.approx(1.0)

    def test_reaches_the_bottom_at_end_of_drawdown(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        assert _at(s, 10) == pytest.approx(0.70)

    def test_halfway_down_is_halfway_through_the_drawdown(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        assert _at(s, 5) == pytest.approx(0.85)

    def test_recovers_fully(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        assert _at(s, 30) == pytest.approx(1.0)

    def test_midpoint_of_recovery(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        assert _at(s, 20) == pytest.approx(0.85)

    def test_never_goes_below_the_severity_floor(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.50, duration_days=10, recovery_days=20)
        worst = min(_at(s, d) for d in range(0, 31))
        assert worst >= 0.50 - 1e-9


class TestRally:
    def test_plateaus_at_the_top(self, db, user):
        s = svc.start_scenario(db, user.id, "rally", 0.25, duration_days=14, recovery_days=1)
        assert _at(s, 14) == pytest.approx(1.25)
        assert _at(s, 40) == pytest.approx(1.25)


class TestLifecycle:
    def test_only_one_scenario_active_at_a_time(self, db, user):
        svc.start_scenario(db, user.id, "crash", -0.30)
        svc.start_scenario(db, user.id, "rally", 0.25)
        active = svc.active_scenario(db, user.id)
        assert active.kind == "rally"

    def test_stop_deactivates(self, db, user):
        svc.start_scenario(db, user.id, "crash", -0.30)
        svc.stop_scenario(db, user.id)
        assert svc.active_scenario(db, user.id) is None

    def test_finished_crash_retires_itself(self, db, user):
        """A fully recovered crash used to stay 'active' forever, leaving the
        banner up and the presets locked until the user pressed stop."""
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=1, recovery_days=1)
        s.started_at = datetime.now(timezone.utc) - timedelta(days=5)
        db.commit()

        assert svc.is_finished(s) is True
        assert svc.active_scenario(db, user.id) is None

    def test_running_crash_is_not_retired(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        assert svc.is_finished(s) is False
        assert svc.active_scenario(db, user.id) is not None

    def test_severity_is_clamped(self, db, user):
        s = svc.start_scenario(db, user.id, "crash", -5.0)
        assert s.severity >= -0.6

    def test_unknown_kind_rejected(self, db, user):
        with pytest.raises(ValueError):
            svc.start_scenario(db, user.id, "apocalypse", -0.3)

    def test_scenarios_are_per_user(self, db, user, seeded_stocks):
        """A crash must not affect anyone else's prices."""
        from app.models import User

        other = User(email="other@example.test", cash=100_000.0)
        db.add(other)
        db.commit()

        svc.start_scenario(db, user.id, "crash", -0.30, duration_days=1, recovery_days=20)
        assert svc.active_scenario(db, other.id) is None


class TestPriceImpact:
    def test_crash_lowers_the_portfolio_value(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 10)
        before = portfolio_service.portfolio_snapshot(db, user)["market_value"]

        s = svc.start_scenario(db, user.id, "crash", -0.30, duration_days=10, recovery_days=20)
        s.started_at = datetime.now(timezone.utc) - timedelta(days=10)
        db.commit()

        after = portfolio_service.portfolio_snapshot(db, user)["market_value"]
        assert after == pytest.approx(before * 0.70, rel=1e-3)

    def test_no_scenario_means_no_adjustment(self, db, user, seeded_stocks):
        quote = portfolio_service.quote_for_user(db, user, "TCS.NS")
        assert quote["scenario_multiplier"] == 1.0
        assert quote["price"] == pytest.approx(4000.0)
