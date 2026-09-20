"""Shared test fixtures.

Two things every test here depends on:

1. An isolated in-memory database, so tests never touch ``data/dolfin.db``.
2. A stubbed market feed. The real one scrapes Yahoo Finance, which would make
   the suite slow, network-dependent and non-deterministic — a test that fails
   because Yahoo rate-limited us teaches nothing.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base
from app.models import Stock, User
from app.services import market as market_service

# Prices the fake feed returns. Round numbers keep the arithmetic in
# assertions obvious.
FAKE_PRICES: dict[str, float] = {
    "TCS.NS": 4000.0,
    "INFY.NS": 1500.0,
    "HDFCBANK.NS": 1600.0,
    "SUNPHARMA.NS": 1200.0,
    "RELIANCE.NS": 1300.0,
    "TATASTEEL.NS": 150.0,
    "ITC.NS": 400.0,
    "NIFTYBEES.NS": 250.0,
}


@pytest.fixture
def db():
    """A fresh in-memory database per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def fake_market(monkeypatch):
    """Replace the Yahoo-backed quote feed with deterministic prices."""

    def _quote(symbol: str, *, force_refresh: bool = False):
        sym = market_service.normalize_symbol(symbol)
        if sym not in FAKE_PRICES:
            raise LookupError(f"No price available for {sym}")
        price = FAKE_PRICES[sym]
        return market_service.Quote(
            symbol=sym,
            price=price,
            currency="INR",
            name=None,
            exchange="NSE",
            previous_close=price,
            day_change=0.0,
            day_change_pct=0.0,
            fetched_at=int(time.time()),
        )

    monkeypatch.setattr(market_service, "get_quote", _quote)
    # The FOMO rule reads price history; default to "no history" so it stays
    # quiet unless a test opts in.
    monkeypatch.setattr(market_service, "get_history", lambda *a, **k: None)
    return FAKE_PRICES


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """Replace the single network seam in the LLM gateway.

    ``autouse`` so no test can accidentally reach the network — one forgotten
    fixture would reintroduce flakiness, so this is on by default rather than
    opt-in. Mirrors the ``fake_market`` pattern above.

    By default the gateway reports *unavailable*, so every test exercises the
    deterministic fallback path unless it opts in via the ``llm`` fixture below.

    The key is blanked explicitly rather than relying on the environment not
    having one. That distinction bit us: the suite passed only because no ``.env``
    existed, and the moment a real key was added, every "behaves without a key"
    test started seeing one — and the embedding ranker became willing to make real
    network calls and spend real quota from a unit test.
    """
    from app.services import llm_gateway

    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)
    llm_gateway.reset_state()

    def _refuse(prompt: str, *, timeout: float) -> str:
        raise AssertionError(
            "A test reached _call_model without opting in. Use the `llm` fixture."
        )

    def _refuse_embed(texts):
        raise AssertionError(
            "A test reached embed_texts without opting in. Embeddings are a network "
            "call; assert on the lexical ranker or stub this explicitly."
        )

    monkeypatch.setattr(llm_gateway, "_call_model", _refuse)
    # The second network seam. Guarded for the same reason as the first.
    from app.services import ranking

    monkeypatch.setattr(ranking, "embed_texts", _refuse_embed)
    yield
    llm_gateway.reset_state()


@pytest.fixture
def llm(monkeypatch):
    """Opt in to a working stubbed LLM.

    Returns a controller so a test can set the reply, force an error, or inspect
    the prompts that were assembled.
    """
    from app.services import llm_gateway

    class Controller:
        def __init__(self) -> None:
            self.reply = "A calm, plain-language explanation of the concern."
            self.error: Exception | None = None
            self.prompts: list[str] = []
            self.calls = 0

        def _call(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            self.prompts.append(prompt)
            if self.error is not None:
                raise self.error
            return self.reply

    ctrl = Controller()
    monkeypatch.setattr(llm_gateway, "_call_model", ctrl._call)
    # A key must appear present for the gateway to attempt a call at all.
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    llm_gateway.reset_state()
    return ctrl


@pytest.fixture
def seeded_stocks(db):
    """The subset of the catalogue the tests trade against."""
    rows = [
        Stock(symbol="TCS.NS", name="TCS", sector="IT", market_cap_band="large", risk_level="low"),
        Stock(symbol="INFY.NS", name="Infosys", sector="IT", market_cap_band="large", risk_level="low"),
        Stock(symbol="HDFCBANK.NS", name="HDFC Bank", sector="Banking", market_cap_band="large", risk_level="low"),
        Stock(symbol="SUNPHARMA.NS", name="Sun Pharma", sector="Pharma", market_cap_band="large", risk_level="medium"),
        Stock(symbol="RELIANCE.NS", name="Reliance", sector="Energy", market_cap_band="large", risk_level="medium"),
        Stock(symbol="TATASTEEL.NS", name="Tata Steel", sector="Metals", market_cap_band="large", risk_level="high"),
        Stock(symbol="ITC.NS", name="ITC", sector="FMCG", market_cap_band="large", risk_level="low"),
        Stock(symbol="NIFTYBEES.NS", name="Nifty 50 ETF", sector="Index Fund", market_cap_band="index", risk_level="low"),
    ]
    db.add_all(rows)
    db.commit()
    return rows


@pytest.fixture
def user(db):
    u = User(
        email="learner@example.test",
        display_name="Learner",
        persona="teen",
        risk_appetite="low",
        language="en",
        cash=100_000.0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
