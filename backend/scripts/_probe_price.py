"""Why can't we price TATAMOTORS.NS?"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import market as market_service

SYMBOLS = ["TATAMOTORS", "TATAMOTORS.NS", "TCS.NS", "TATASTEEL.NS", "TATAELXSI.NS"]

print("=== via our service ===")
for s in SYMBOLS:
    try:
        q = market_service.get_quote(s, force_refresh=True)
        print(f"  {s:18} OK   {q.price:>10,.2f}  stale={getattr(q, 'stale', False)}")
    except Exception as e:
        print(f"  {s:18} FAIL {type(e).__name__}: {str(e)[:80]}")

print("\n=== raw yfinance, to separate our bug from theirs ===")
import yfinance as yf

for s in ["TATAMOTORS.NS", "TATAMOTORSPV.NS", "TMPV.NS", "TATAMTRDVR.NS"]:
    try:
        t = yf.Ticker(s)
        fi = getattr(t, "fast_info", None)
        price = None
        if fi:
            for key in ("last_price", "lastPrice", "regularMarketPrice"):
                try:
                    price = fi[key] if not hasattr(fi, key) else getattr(fi, key)
                    if price:
                        break
                except Exception:
                    continue
        hist = t.history(period="5d")
        h = None if hist is None or hist.empty else float(hist["Close"].dropna().iloc[-1])
        print(f"  {s:18} fast_info={price}  history_close={h}")
    except Exception as e:
        print(f"  {s:18} {type(e).__name__}: {str(e)[:90]}")
