"""Market data API."""

from fastapi import APIRouter, HTTPException, Query

from app.services import market as market_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/quote/{symbol}")
def quote(symbol: str, refresh: bool = Query(False, description="Bypass cache")):
    try:
        q = market_service.get_quote(symbol, force_refresh=refresh)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return q


@router.get("/quotes")
def quotes(symbols: str = Query(..., description="Comma-separated list, e.g. RELIANCE,TCS,INFY")):
    items = [s for s in (sym.strip() for sym in symbols.split(",")) if s]
    if not items:
        raise HTTPException(status_code=400, detail="No symbols provided")
    return market_service.get_quotes(items)


@router.get("/history/{symbol}")
def history(
    symbol: str,
    period: str = Query("1mo", description="yfinance period: 5d, 1mo, 3mo, 6mo, 1y, 5y, max"),
    interval: str = Query("1d", description="yfinance interval: 1d, 1wk, 1mo"),
):
    """Return OHLCV bars for the symbol — used for charts on the frontend."""
    try:
        df = market_service.get_history(symbol, period=period, interval=interval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No history for {symbol}")
    out = []
    for idx, row in df.iterrows():
        out.append({
            "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row.get("Volume", 0) or 0),
        })
    return out
