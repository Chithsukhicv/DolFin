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
