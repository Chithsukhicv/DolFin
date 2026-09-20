"""Check every catalogue symbol against the live feed.

Corporate actions retire tickers — Tata Motors became TMPV after its 2025
demerger, and the old symbol simply stopped returning data. A dead symbol in the
catalogue is worse than an absent one: it is browsable, clickable, and fails only
at the moment a learner tries to trade it.

Usage, from ``backend/``:

    python scripts/audit_catalogue.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.stocks_seed import SEED_STOCKS
from app.services import market as market_service


def main() -> int:
    dead: list[tuple[str, str]] = []
    ok = 0

    print(f"Checking {len(SEED_STOCKS)} catalogue symbols against the live feed…\n")
    for row in SEED_STOCKS:
        symbol = row["symbol"]
        try:
            quote = market_service.get_quote(symbol, force_refresh=True)
            ok += 1
            flag = " (stale cache)" if getattr(quote, "stale", False) else ""
            print(f"  OK    {symbol:18} {quote.price:>12,.2f}{flag}")
        except Exception as e:
            dead.append((symbol, f"{type(e).__name__}: {str(e)[:70]}"))
            print(f"  DEAD  {symbol:18} {row['name']}")

    print(f"\n{ok} priced, {len(dead)} unpriceable")
    if dead:
        print("\nThese need replacing in app/data/stocks_seed.py:")
        for symbol, reason in dead:
            print(f"  {symbol:18} {reason}")
        return 1
    print("Every catalogue symbol is priceable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
