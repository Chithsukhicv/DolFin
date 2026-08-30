"""Market data service backed by yfinance with a SQLite price cache.

Symbol convention:
- NSE: append ``.NS`` (e.g. ``RELIANCE.NS``)
- BSE: append ``.BO`` (e.g. ``RELIANCE.BO``)

This module is intentionally synchronous; FastAPI runs it in a threadpool.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yfinance as yf
from curl_cffi import requests as curl_requests

from app.config import get_settings

log = logging.getLogger(__name__)

# Cache TTL for live quotes (seconds). Keeps Yahoo calls bounded.
QUOTE_TTL_SECONDS = 60

# Yahoo Finance has been blocking plain `requests` sessions; curl_cffi
# impersonates a real Chrome client and stays under the radar.
_session = curl_requests.Session(impersonate="chrome")


@dataclass
class Quote:
    symbol: str
    price: float
    currency: str
    name: str | None
    exchange: str | None
    previous_close: float | None
    day_change: float | None
    day_change_pct: float | None
    fetched_at: int  # epoch seconds
    # True when Yahoo failed and we served an expired cache entry instead of
    # erroring. The frontend can show a "delayed price" hint.
    stale: bool = False


def _db_path() -> Path:
    settings = get_settings()
    path = (settings.project_root / settings.price_db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _conn():
    path = _db_path()
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """Create cache tables if missing."""
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS quote_cache (
                symbol         TEXT PRIMARY KEY,
                price          REAL NOT NULL,
                currency       TEXT,
                name           TEXT,
                exchange       TEXT,
                previous_close REAL,
                day_change     REAL,
                day_change_pct REAL,
                fetched_at     INTEGER NOT NULL
            );
            """
        )


def normalize_symbol(symbol: str) -> str:
    """Normalize a user-supplied symbol.

    Defaults to NSE (``.NS``) when no exchange suffix is present.
    """
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol cannot be empty")
    if "." in s:
        return s
    return f"{s}.NS"


def _row_to_quote(row: sqlite3.Row) -> Quote:
    return Quote(
        symbol=row["symbol"],
        price=row["price"],
        currency=row["currency"],
        name=row["name"],
        exchange=row["exchange"],
        previous_close=row["previous_close"],
        day_change=row["day_change"],
        day_change_pct=row["day_change_pct"],
        fetched_at=row["fetched_at"],
    )


def _read_cache(symbol: str) -> Quote | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM quote_cache WHERE symbol = ?", (symbol,)
        ).fetchone()
    return _row_to_quote(row) if row else None


def _write_cache(q: Quote) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO quote_cache (
                symbol, price, currency, name, exchange,
                previous_close, day_change, day_change_pct, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                price          = excluded.price,
                currency       = excluded.currency,
                name           = excluded.name,
                exchange       = excluded.exchange,
                previous_close = excluded.previous_close,
                day_change     = excluded.day_change,
                day_change_pct = excluded.day_change_pct,
                fetched_at     = excluded.fetched_at
            """,
            (
                q.symbol,
                q.price,
                q.currency,
                q.name,
                q.exchange,
                q.previous_close,
                q.day_change,
                q.day_change_pct,
                q.fetched_at,
            ),
        )


def _safe(fn, default=None):
    """Run a yfinance call that is allowed to fail without killing the request."""
    try:
        return fn()
    except Exception as e:  # yfinance/Yahoo are routinely flaky
        log.debug("yfinance call failed: %s", e)
        return default


def _price_from_fast_info(ticker) -> tuple[float | None, float | None, str | None, str | None]:
    fast = _safe(lambda: ticker.fast_info) or {}

    def pick(*keys):
        for k in keys:
            val = _safe(lambda k=k: fast.get(k))
            if val:
                return val
        return None

    return (
        pick("last_price", "lastPrice"),
        pick("previous_close", "previousClose"),
        pick("currency"),
        pick("exchange"),
    )


def _price_from_history(ticker) -> tuple[float | None, float | None]:
    """Most reliable fallback: the daily bars endpoint.

    `fast_info` and `.info` both scrape quote endpoints that Yahoo throttles
    aggressively. The chart/history endpoint holds up far better, so when the
    quote path returns nothing we read the last two closes instead.
    """
    df = _safe(lambda: ticker.history(period="5d", interval="1d", auto_adjust=False))
    if df is None or getattr(df, "empty", True):
        return None, None
    closes = df["Close"].dropna()
    if closes.empty:
        return None, None
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
    return price, prev


def _fetch_from_yahoo(symbol: str) -> Quote:
    ticker = yf.Ticker(symbol, session=_session)

    price, prev_close, currency, exchange = _price_from_fast_info(ticker)

    # Fallback 1: daily bars (survives quote-endpoint throttling).
    if price is None:
        price, hist_prev = _price_from_history(ticker)
        prev_close = prev_close or hist_prev

    # Fallback 2: the slow `.info` blob, guarded so a failure cannot 500.
    if price is None:
        info = _safe(lambda: ticker.info) or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = prev_close or info.get("regularMarketPreviousClose")
        currency = currency or info.get("currency")
        exchange = exchange or info.get("exchange")

    if price is None:
        raise LookupError(f"No price available for {symbol}")

    # Name is cosmetic and comes from our own seeded catalog on the frontend,
    # so it must never be the reason a quote fails.
    name = None
    if prev_close is None:
        _, prev_close = _price_from_history(ticker)

    price = float(price)
    prev_close = float(prev_close) if prev_close else None
    day_change = (price - prev_close) if prev_close else None
    day_change_pct = (
        (day_change / prev_close * 100.0) if (day_change is not None and prev_close) else None
    )

    return Quote(
        symbol=symbol,
        price=price,
        currency=currency or "INR",
        name=name,
        exchange=exchange,
        previous_close=prev_close,
        day_change=float(day_change) if day_change is not None else None,
        day_change_pct=float(day_change_pct) if day_change_pct is not None else None,
        fetched_at=int(time.time()),
    )


def get_quote(symbol: str, *, force_refresh: bool = False) -> Quote:
    """Return a quote, using the cache when fresh.

    If Yahoo fails we fall back to an expired cache entry (flagged ``stale``)
    rather than raising. A slightly old price is far more useful to a learner
    than a blank row, and it keeps one throttled symbol from breaking the
    whole market page.
    """
    sym = normalize_symbol(symbol)
    init_db()

    cached = _read_cache(sym)
    if not force_refresh and cached and (time.time() - cached.fetched_at) < QUOTE_TTL_SECONDS:
        return cached

    try:
        quote = _fetch_from_yahoo(sym)
    except Exception as e:
        if cached:
            log.warning("Quote fetch failed for %s (%s) — serving stale cache.", sym, e)
            cached.stale = True
            return cached
        raise LookupError(f"No price available for {sym}") from e

    _write_cache(quote)
    return quote


def get_quotes(symbols: Iterable[str]) -> list[Quote]:
    """Batch quotes, skipping symbols that have no price at all.

    One bad symbol should never blank out the entire market page, so failures
    are logged and dropped instead of propagated.
    """
    out: list[Quote] = []
    for s in symbols:
        try:
            out.append(get_quote(s))
        except Exception as e:
            log.warning("Skipping quote for %s: %s", s, e)
    return out


def get_history(symbol: str, *, period: str = "1mo", interval: str = "1d"):
    """Return a pandas DataFrame of historical OHLCV data for the symbol.

    Used by behavioural rules (e.g. FOMO detection looking at the last few days).
    """
    sym = normalize_symbol(symbol)
    ticker = yf.Ticker(sym, session=_session)
    df = ticker.history(period=period, interval=interval, auto_adjust=False)
    return df
