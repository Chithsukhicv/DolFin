"""Portfolio engine: cash, average cost, P&L, and resilience to bad quotes."""

from __future__ import annotations

import pytest

from app.services import market as market_service
from app.services import portfolio as portfolio_service


class TestBuy:
    def test_deducts_cash_including_fee(self, db, user, seeded_stocks):
        result = portfolio_service.execute_buy(db, user, "TCS.NS", 10)
        gross = 4000.0 * 10
        expected_fee = gross * (portfolio_service.FEE_BPS / 10_000)
        assert result.transaction.fee == pytest.approx(expected_fee)
        assert result.cash_after == pytest.approx(100_000.0 - gross - expected_fee)

    def test_rejects_a_purchase_beyond_available_cash(self, db, user, seeded_stocks):
        with pytest.raises(ValueError, match="Insufficient cash"):
            portfolio_service.execute_buy(db, user, "TCS.NS", 1000)

    def test_rejects_non_positive_quantity(self, db, user, seeded_stocks):
        with pytest.raises(ValueError, match="positive"):
            portfolio_service.execute_buy(db, user, "TCS.NS", 0)

    def test_average_cost_is_volume_weighted(self, db, user, seeded_stocks, monkeypatch):
        portfolio_service.execute_buy(db, user, "INFY.NS", 10)  # at 1500

        # Second purchase at a different price.
        original = market_service.get_quote

        def cheaper(symbol, *, force_refresh=False):
            q = original(symbol)
            if q.symbol == "INFY.NS":
                q.price = 1000.0
            return q

        monkeypatch.setattr(market_service, "get_quote", cheaper)
        result = portfolio_service.execute_buy(db, user, "INFY.NS", 10)

        # 10 @ 1500 + 10 @ 1000 → average 1250
        assert result.avg_cost == pytest.approx(1250.0)
        assert result.holding_quantity == pytest.approx(20)


class TestSell:
    def test_credits_proceeds_net_of_fee(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 10)
        cash_before = user.cash
        result = portfolio_service.execute_sell(db, user, "TCS.NS", 5)

        gross = 4000.0 * 5
        fee = gross * (portfolio_service.FEE_BPS / 10_000)
        assert result.cash_after == pytest.approx(cash_before + gross - fee)

    def test_cannot_sell_more_than_held(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        with pytest.raises(ValueError, match="only"):
            portfolio_service.execute_sell(db, user, "TCS.NS", 10)

    def test_cannot_sell_what_is_not_owned(self, db, user, seeded_stocks):
        with pytest.raises(ValueError):
            portfolio_service.execute_sell(db, user, "TCS.NS", 1)

    def test_holding_removed_when_fully_sold(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        result = portfolio_service.execute_sell(db, user, "TCS.NS", 5)
        assert result.holding_quantity == 0
        snap = portfolio_service.portfolio_snapshot(db, user)
        assert snap["holdings"] == []

    def test_realised_pnl_recorded_on_profit(self, db, user, seeded_stocks, monkeypatch):
        portfolio_service.execute_buy(db, user, "INFY.NS", 10)  # at 1500

        original = market_service.get_quote

        def higher(symbol, *, force_refresh=False):
            q = original(symbol)
            if q.symbol == "INFY.NS":
                q.price = 2000.0
            return q

        monkeypatch.setattr(market_service, "get_quote", higher)
        result = portfolio_service.execute_sell(db, user, "INFY.NS", 10)
        # (2000 - 1500) * 10, less the sell fee
        assert result.transaction.realised_pnl > 4_900


class TestSnapshot:
    def test_totals_add_up(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        portfolio_service.execute_buy(db, user, "HDFCBANK.NS", 5)
        snap = portfolio_service.portfolio_snapshot(db, user)

        assert snap["total_value"] == pytest.approx(snap["cash"] + snap["market_value"])
        assert len(snap["holdings"]) == 2

    def test_sector_allocation_sums_to_a_hundred(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        portfolio_service.execute_buy(db, user, "HDFCBANK.NS", 5)
        snap = portfolio_service.portfolio_snapshot(db, user)
        assert sum(snap["sector_allocation_pct"].values()) == pytest.approx(100.0)

    def test_holding_survives_a_failed_quote(self, db, user, seeded_stocks, monkeypatch):
        """A throttled quote used to make the position vanish from the UI and
        from every downstream score."""
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        portfolio_service.execute_buy(db, user, "HDFCBANK.NS", 5)

        original = market_service.get_quote

        def flaky(symbol, *, force_refresh=False):
            if market_service.normalize_symbol(symbol) == "TCS.NS":
                raise LookupError("throttled")
            return original(symbol)

        monkeypatch.setattr(market_service, "get_quote", flaky)
        snap = portfolio_service.portfolio_snapshot(db, user)

        assert len(snap["holdings"]) == 2, "position disappeared when its quote failed"
        tcs = next(h for h in snap["holdings"] if h["symbol"] == "TCS.NS")
        assert tcs["price_unavailable"] is True
        assert snap["stale_price_count"] >= 1

    def test_empty_portfolio_is_valued_as_cash(self, db, user, seeded_stocks):
        snap = portfolio_service.portfolio_snapshot(db, user)
        assert snap["market_value"] == 0
        assert snap["total_value"] == pytest.approx(100_000.0)
        assert snap["sector_allocation_pct"] == {}


class TestReset:
    def test_reset_restores_starting_cash_and_clears_holdings(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 5)
        portfolio_service.reset_user_portfolio(db, user, starting_cash=100_000.0)

        snap = portfolio_service.portfolio_snapshot(db, user)
        assert snap["cash"] == pytest.approx(100_000.0)
        assert snap["holdings"] == []
