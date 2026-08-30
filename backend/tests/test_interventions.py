"""Intervention engine: rule firing and the preview lifecycle.

The lifecycle tests guard the bug that broke the core learning loop. Warnings
used to be written only when a trade *executed*, so cancelling left nothing to
mark as heeded and "Cancel & reflect" silently did nothing — or worse, rewrote
the history of an earlier trade.
"""

from __future__ import annotations

from app.models import InterventionLog
from app.services import interventions as svc
from app.services import portfolio as portfolio_service
from app.services import scenarios as scenarios_service


def _fired_ids(fired):
    return {i.rule_id for i in fired}


class TestConcentration:
    def test_fires_when_one_stock_would_dominate(self, db, user, seeded_stocks):
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 10)
        assert "concentration" in _fired_ids(fired)

    def test_critical_above_thirty_percent(self, db, user, seeded_stocks):
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 20)
        rule = next(i for i in fired if i.rule_id == "concentration")
        assert rule.severity == "critical"

    def test_quiet_when_spread_out(self, db, user, seeded_stocks):
        for symbol, qty in [
            ("TCS.NS", 4), ("INFY.NS", 10), ("HDFCBANK.NS", 9),
            ("SUNPHARMA.NS", 12), ("RELIANCE.NS", 11), ("ITC.NS", 37),
        ]:
            portfolio_service.execute_buy(db, user, symbol, qty)
        fired = svc.evaluate_pre_trade(db, user, "ITC.NS", "buy", 1)
        assert "concentration" not in _fired_ids(fired)

    def test_index_etf_is_not_treated_as_a_single_stock(self, db, user, seeded_stocks):
        """Warning someone for buying an index fund teaches the wrong lesson."""
        fired = svc.evaluate_pre_trade(db, user, "NIFTYBEES.NS", "buy", 100)
        concentration = [i for i in fired if i.rule_id == "concentration"]
        assert not concentration or concentration[0].severity == "info"


class TestVolatilityMismatch:
    def test_low_risk_user_warned_on_high_risk_stock(self, db, user, seeded_stocks):
        assert user.risk_appetite == "low"
        fired = svc.evaluate_pre_trade(db, user, "TATASTEEL.NS", "buy", 10)
        assert "volatility_mismatch" in _fired_ids(fired)

    def test_no_warning_on_matching_risk(self, db, user, seeded_stocks):
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 1)
        assert "volatility_mismatch" not in _fired_ids(fired)


class TestPanicSell:
    def test_fires_during_a_crash(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        scenarios_service.start_scenario(db, user.id, "crash", -0.30)
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "sell", 5)
        rule = next(i for i in fired if i.rule_id == "panic_sell")
        assert rule.severity == "critical"
        assert rule.concept == "panic_selling"

    def test_silent_without_a_scenario(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "sell", 5)
        assert "panic_sell" not in _fired_ids(fired)

    def test_silent_during_a_rally(self, db, user, seeded_stocks):
        """A rally is not a reason to warn about panic selling."""
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        scenarios_service.start_scenario(db, user.id, "rally", 0.25)
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "sell", 5)
        assert "panic_sell" not in _fired_ids(fired)


class TestSeverityOrdering:
    def test_critical_comes_first(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        scenarios_service.start_scenario(db, user.id, "crash", -0.30)
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "sell", 5)
        assert fired[0].severity == "critical"


class TestPreviewLifecycle:
    def test_logged_as_pending_at_preview(self, db, user, seeded_stocks):
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 10)
        svc.log_interventions(db, user, fired, preview_id="prev1")

        rows = db.query(InterventionLog).filter_by(preview_id="prev1").all()
        assert rows
        assert all(r.user_action == "pending" for r in rows)

    def test_heeding_marks_only_this_preview(self, db, user, seeded_stocks):
        """The old rule_id lookup could rewrite an earlier trade's history."""
        first = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 10)
        svc.log_interventions(db, user, first, preview_id="old", user_action="ignored")
        second = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 10)
        svc.log_interventions(db, user, second, preview_id="new")

        updated = svc.resolve_preview(db, user, "new", "heeded")
        assert updated > 0

        old_rows = db.query(InterventionLog).filter_by(preview_id="old").all()
        assert all(r.user_action == "ignored" for r in old_rows), "earlier trade was rewritten"
        new_rows = db.query(InterventionLog).filter_by(preview_id="new").all()
        assert all(r.user_action == "heeded" for r in new_rows)

    def test_resolving_is_idempotent(self, db, user, seeded_stocks):
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 10)
        svc.log_interventions(db, user, fired, preview_id="p1")

        assert svc.resolve_preview(db, user, "p1", "heeded") > 0
        # Already resolved, so a repeat must not flip it to ignored.
        assert svc.resolve_preview(db, user, "p1", "ignored") == 0
        rows = db.query(InterventionLog).filter_by(preview_id="p1").all()
        assert all(r.user_action == "heeded" for r in rows)

    def test_unknown_preview_id_is_a_no_op(self, db, user, seeded_stocks):
        assert svc.resolve_preview(db, user, "does-not-exist", "heeded") == 0
        assert svc.resolve_preview(db, user, "", "heeded") == 0

    def test_another_users_warnings_are_untouched(self, db, user, seeded_stocks):
        from app.models import User

        other = User(email="other@example.test", cash=100_000.0)
        db.add(other)
        db.commit()

        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 10)
        svc.log_interventions(db, user, fired, preview_id="shared")

        assert svc.resolve_preview(db, other, "shared", "heeded") == 0
        rows = db.query(InterventionLog).filter_by(preview_id="shared").all()
        assert all(r.user_action == "pending" for r in rows)


class TestMarketDataGaps:
    """Yahoo returns NaN rows for non-trading days and gaps on thin symbols.

    NaN fails every comparison, so `run < 0.15` was False and the FOMO rule
    fired on a nan value — a spurious warning that also made the preview
    response unserialisable and returned an opaque 500.
    """

    def test_nan_history_does_not_fire_fomo(self, db, user, seeded_stocks, monkeypatch):
        import pandas as pd

        from app.services import market as market_service

        nan_series = pd.DataFrame(
            {"Close": [100.0, float("nan"), float("nan"), 101.0, float("nan"), float("nan")]}
        )
        monkeypatch.setattr(market_service, "get_history", lambda *a, **k: nan_series)

        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 1)
        assert "fomo" not in {i.rule_id for i in fired}

    def test_all_context_values_are_json_safe(self, db, user, seeded_stocks, monkeypatch):
        import json

        import pandas as pd

        from app.services import market as market_service

        # A run-up big enough to fire, but with NaN padding around it.
        series = pd.DataFrame(
            {"Close": [100.0, float("nan"), 105.0, 110.0, 118.0, 125.0, 130.0]}
        )
        monkeypatch.setattr(market_service, "get_history", lambda *a, **k: series)

        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 1)
        for i in fired:
            # allow_nan=False makes json.dumps raise on NaN/Infinity.
            json.dumps(i.to_dict(), allow_nan=False)

    def test_genuine_runup_still_fires(self, db, user, seeded_stocks, monkeypatch):
        """The NaN guard must not silence the rule for real run-ups."""
        import pandas as pd

        from app.services import market as market_service

        series = pd.DataFrame({"Close": [100.0, 104.0, 109.0, 115.0, 121.0, 128.0, 135.0]})
        monkeypatch.setattr(market_service, "get_history", lambda *a, **k: series)

        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 1)
        assert "fomo" in {i.rule_id for i in fired}

    def test_missing_history_is_tolerated(self, db, user, seeded_stocks, monkeypatch):
        from app.services import market as market_service

        monkeypatch.setattr(
            market_service, "get_history",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Yahoo down")),
        )
        fired = svc.evaluate_pre_trade(db, user, "TCS.NS", "buy", 1)
        assert "fomo" not in {i.rule_id for i in fired}
