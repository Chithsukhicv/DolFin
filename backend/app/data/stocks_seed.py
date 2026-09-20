"""Hand-curated seed list of NSE stocks with sector + cap classification.

Kept small and well-known on purpose so the diversification rules have
clean signal in the demo. Symbols use yfinance's ``.NS`` suffix.
"""

from __future__ import annotations


SEED_STOCKS: list[dict] = [
    # IT
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "WIPRO.NS", "name": "Wipro", "sector": "IT", "market_cap_band": "large", "risk_level": "medium"},
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT", "market_cap_band": "large", "risk_level": "low"},

    # Banking & Financials
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "sector": "Banking", "market_cap_band": "large", "risk_level": "medium"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Banking", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "Financials", "market_cap_band": "large", "risk_level": "medium"},

    # Energy / Oil & Gas
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy", "market_cap_band": "large", "risk_level": "medium"},
    {"symbol": "ONGC.NS", "name": "Oil and Natural Gas Corporation", "sector": "Energy", "market_cap_band": "large", "risk_level": "medium"},

    # FMCG
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "FMCG", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "ITC.NS", "name": "ITC", "sector": "FMCG", "market_cap_band": "large", "risk_level": "low"},
    {"symbol": "NESTLEIND.NS", "name": "Nestle India", "sector": "FMCG", "market_cap_band": "large", "risk_level": "low"},

    # Auto
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Auto", "market_cap_band": "large", "risk_level": "medium"},
    # Tata Motors demerged in late 2025: the passenger-vehicle business kept the
    # listing and now trades as TMPV, while the commercial-vehicle arm listed
    # separately. TATAMOTORS.NS returns no data at all — run
    # scripts/audit_catalogue.py to catch this class of breakage, because a dead
    # symbol stays browsable and only fails at the moment someone tries to trade it.
    {"symbol": "TMPV.NS", "name": "Tata Motors Passenger Vehicles", "sector": "Auto", "market_cap_band": "large", "risk_level": "high"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Auto", "market_cap_band": "large", "risk_level": "medium"},

    # Pharma
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharmaceutical", "sector": "Pharma", "market_cap_band": "large", "risk_level": "medium"},
    {"symbol": "DRREDDY.NS", "name": "Dr. Reddy's Laboratories", "sector": "Pharma", "market_cap_band": "large", "risk_level": "medium"},

    # Telecom
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom", "market_cap_band": "large", "risk_level": "medium"},

    # Consumer & retail
    {"symbol": "TITAN.NS", "name": "Titan Company", "sector": "Consumer", "market_cap_band": "large", "risk_level": "medium"},
    {"symbol": "ASIANPAINT.NS", "name": "Asian Paints", "sector": "Consumer", "market_cap_band": "large", "risk_level": "low"},

    # Infra / Cement
    {"symbol": "LT.NS", "name": "Larsen & Toubro", "sector": "Infrastructure", "market_cap_band": "large", "risk_level": "medium"},
    {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Cement", "market_cap_band": "large", "risk_level": "medium"},

    # Metals
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel", "sector": "Metals", "market_cap_band": "large", "risk_level": "high"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel", "sector": "Metals", "market_cap_band": "large", "risk_level": "high"},

    # Mid-cap names, so the mid/small vocabulary in the UI is not purely decorative
    # and the volatility-mismatch rule has something to actually fire on.
    {"symbol": "TATAELXSI.NS", "name": "Tata Elxsi", "sector": "IT", "market_cap_band": "mid", "risk_level": "high"},
    {"symbol": "FEDERALBNK.NS", "name": "Federal Bank", "sector": "Banking", "market_cap_band": "mid", "risk_level": "medium"},
    {"symbol": "ASHOKLEY.NS", "name": "Ashok Leyland", "sector": "Auto", "market_cap_band": "mid", "risk_level": "high"},
    {"symbol": "LICHSGFIN.NS", "name": "LIC Housing Finance", "sector": "Financials", "market_cap_band": "mid", "risk_level": "high"},

    # Index ETFs. Without these, the SIP, rupee-cost-averaging and index-fund
    # concepts could be taught in the library and quizzes but never practised.
    # They sit in their own "Index Fund" sector because each one already holds
    # dozens of companies, so the concentration rules should treat them as
    # diversified rather than as a single-company bet.
    {"symbol": "NIFTYBEES.NS", "name": "Nippon India Nifty 50 ETF", "sector": "Index Fund", "market_cap_band": "index", "risk_level": "low"},
    {"symbol": "JUNIORBEES.NS", "name": "Nippon India Nifty Next 50 ETF", "sector": "Index Fund", "market_cap_band": "index", "risk_level": "medium"},
    {"symbol": "BANKBEES.NS", "name": "Nippon India Nifty Bank ETF", "sector": "Index Fund", "market_cap_band": "index", "risk_level": "medium"},
    {"symbol": "SETFNIF50.NS", "name": "SBI Nifty 50 ETF", "sector": "Index Fund", "market_cap_band": "index", "risk_level": "low"},
    {"symbol": "MON100.NS", "name": "Motilal Oswal Nasdaq 100 ETF", "sector": "Index Fund", "market_cap_band": "index", "risk_level": "medium"},
]

# Symbols that represent baskets rather than single companies. The concentration
# rule uses this to avoid warning a learner for doing the sensible thing: an
# index ETF at 40% of a portfolio is not the same risk as one company at 40%.
DIVERSIFIED_SYMBOLS: set[str] = {
    s["symbol"] for s in SEED_STOCKS if s["sector"] == "Index Fund"
}


def is_diversified_instrument(symbol: str) -> bool:
    return symbol in DIVERSIFIED_SYMBOLS


def sync_catalogue(session) -> dict:
    """Reconcile the stocks table with ``SEED_STOCKS``.

    Insert-only was not enough. Corporate actions retire tickers — Tata Motors
    became TMPV after its 2025 demerger — and a retired symbol left in the table
    stays fully browsable, searchable and clickable, then fails only at the moment
    a learner tries to price or trade it. That is a worse failure than the symbol
    simply not being there.

    So this also updates changed metadata and removes symbols that have dropped
    out of the seed list. Removal is skipped for any symbol a learner still holds
    or has traded: deleting it would orphan their holding and silently rewrite
    their history. Those are logged instead, and the portfolio snapshot already
    survives an unpriceable holding by falling back to cost basis.
    """
    import logging

    from app.models import Holding, Stock, Transaction

    log = logging.getLogger(__name__)

    wanted = {s["symbol"]: s for s in SEED_STOCKS}
    existing = {row.symbol: row for row in session.query(Stock).all()}

    inserted = updated = removed = 0

    for symbol, spec in wanted.items():
        row = existing.get(symbol)
        if row is None:
            session.add(Stock(**spec))
            inserted += 1
            continue
        changed = False
        for field in ("name", "sector", "market_cap_band", "risk_level"):
            if getattr(row, field) != spec[field]:
                setattr(row, field, spec[field])
                changed = True
        if changed:
            updated += 1

    retired = [sym for sym in existing if sym not in wanted]
    kept_because_held: list[str] = []
    for symbol in retired:
        in_use = (
            session.query(Holding).filter_by(symbol=symbol).first() is not None
            or session.query(Transaction).filter_by(symbol=symbol).first() is not None
        )
        if in_use:
            kept_because_held.append(symbol)
            continue
        session.delete(existing[symbol])
        removed += 1

    if inserted or updated or removed:
        session.commit()

    if kept_because_held:
        log.warning(
            "Retired symbols kept because learners still hold or traded them: %s. "
            "Their positions will price from cost basis.",
            ", ".join(sorted(kept_because_held)),
        )

    return {
        "inserted": inserted,
        "updated": updated,
        "removed": removed,
        "kept_because_held": sorted(kept_because_held),
        "total": len(wanted),
    }


def seed_if_empty(session) -> int:
    """Backwards-compatible alias. Prefer ``sync_catalogue``."""
    return sync_catalogue(session)["inserted"]
