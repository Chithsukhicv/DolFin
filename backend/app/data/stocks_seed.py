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
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors", "sector": "Auto", "market_cap_band": "large", "risk_level": "high"},
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


def seed_if_empty(session) -> int:
    """Upsert the catalogue. Returns the number of rows inserted.

    Adds any symbol missing from the table rather than bailing out when the
    table is merely non-empty. The old early-return meant newly added symbols
    (the ETFs and mid-caps) would never appear for anyone with an existing
    database, which is every existing user.
    """
    from app.models import Stock

    existing = {s for (s,) in session.query(Stock.symbol).all()}
    new_rows = [Stock(**s) for s in SEED_STOCKS if s["symbol"] not in existing]
    if not new_rows:
        return 0
    session.add_all(new_rows)
    session.commit()
    return len(new_rows)
