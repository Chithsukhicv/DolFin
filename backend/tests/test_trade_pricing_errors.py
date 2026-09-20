"""What the trade endpoints do when the market feed cannot price a symbol.

R13.2: a preview that cannot produce a quote, a rule evaluation or an estimated
cost must return an error rather than a partial payload. A preview missing its
price is not a degraded preview — the estimated cost is gone and the
concentration, cash-drain and FOMO rules have nothing to compare against, so
several warnings would silently not fire. Showing "no warnings" in that state is
the worst possible answer.

``get_quote`` already falls back to a stale cache before giving up, so reaching
this path means there is no price at all.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import create_app
from app.models import Holding, Stock, User
from app.services import market as market_service


@pytest.fixture
def client(db, seeded_stocks, user):
    """App wired to the test session so the fake market fixture applies."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unpriceable(monkeypatch, db):
    """A catalogue symbol the feed refuses to price, cache included."""
    db.add(Stock(
        symbol="GHOST.NS", name="Ghost Industries", sector="IT",
        market_cap_band="small", risk_level="high",
    ))
    db.commit()

    original = market_service.get_quote

    def failing(symbol: str, *, force_refresh: bool = False):
        if market_service.normalize_symbol(symbol) == "GHOST.NS":
            raise LookupError("No price available for GHOST.NS")
        return original(symbol, force_refresh=force_refresh)

    monkeypatch.setattr(market_service, "get_quote", failing)
    return "GHOST"


class TestPreview:
    def test_an_unpriceable_symbol_is_refused(self, client, user, unpriceable):
        res = client.post("/portfolio/preview", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        assert res.status_code == 503, res.text

    def test_the_error_names_the_symbol(self, client, user, unpriceable):
        res = client.post("/portfolio/preview", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        assert unpriceable in res.json()["detail"]

    def test_no_partial_preview_is_returned(self, client, user, unpriceable):
        """The whole point of R13.2 — no payload with the price missing."""
        res = client.post("/portfolio/preview", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        body = res.json()
        for field in ("quote", "interventions", "blocking", "estimated_cost", "preview_id"):
            assert field not in body, f"partial preview leaked {field}"

    def test_a_priceable_symbol_still_works(self, client, user, unpriceable):
        """The failure must be scoped to the one symbol, not the endpoint."""
        res = client.post("/portfolio/preview", json={
            "user_id": user.id, "symbol": "TCS", "side": "buy", "quantity": 1,
        })
        assert res.status_code == 200
        assert res.json()["quote"]["price"] > 0


class TestExecution:
    def test_buy_is_refused_rather_than_crashing(self, client, user, unpriceable):
        res = client.post("/portfolio/buy", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        assert res.status_code == 503, res.text

    def test_sell_is_refused_rather_than_crashing(self, client, db, user, unpriceable):
        db.add(Holding(user_id=user.id, symbol="GHOST.NS", quantity=5, avg_cost=100.0))
        db.commit()
        res = client.post("/portfolio/sell", json={
            "user_id": user.id, "symbol": unpriceable, "side": "sell", "quantity": 1,
        })
        assert res.status_code == 503, res.text

    def test_a_refused_buy_leaves_cash_untouched(self, client, db, user, unpriceable):
        before = user.cash
        client.post("/portfolio/buy", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        db.refresh(user)
        assert user.cash == before

    def test_a_refused_trade_writes_no_transaction(self, client, db, user, unpriceable):
        from app.models import Transaction

        before = db.query(Transaction).count()
        client.post("/portfolio/buy", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        assert db.query(Transaction).count() == before

    def test_a_refused_trade_writes_no_intervention_log(self, client, db, user, unpriceable):
        """A warning recorded against a trade that never happened would skew the score."""
        from app.models import InterventionLog

        before = db.query(InterventionLog).count()
        client.post("/portfolio/preview", json={
            "user_id": user.id, "symbol": unpriceable, "side": "buy", "quantity": 1,
        })
        assert db.query(InterventionLog).count() == before


class TestUnknownUser:
    def test_preview_for_a_missing_user_is_404(self, client):
        """R11.8."""
        res = client.post("/portfolio/preview", json={
            "user_id": "nope", "symbol": "TCS", "side": "buy", "quantity": 1,
        })
        assert res.status_code == 404

    @pytest.mark.parametrize("path", [
        "/coach/patterns/nope",
        "/coach/evidence/nope",
        "/learn/path/nope",
        "/quizzes/adaptive/nope",
        "/quizzes/adaptive/nope/panic_selling",
        "/chat/sessions/nope",
    ])
    def test_ai_endpoints_404_for_a_missing_user(self, client, path):
        """R11.8 across the AI surface."""
        assert client.get(path).status_code == 404

    def test_chat_ask_404s_for_a_missing_user(self, client):
        res = client.post("/chat/ask", json={
            "user_id": "nope", "question": "what is diversification?",
        })
        assert res.status_code == 404
