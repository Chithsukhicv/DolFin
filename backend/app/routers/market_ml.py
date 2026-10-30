"""Market Movement Predictor — forecast API router.

Exposes:
    GET /market-ml/{symbol}/forecast

Returns a MarketForecastResponse with UP/SIDEWAYS/DOWN probabilities for
the 1-, 3-, 5-, and 10-trading-day horizons.  All error states are surfaced
via the ``model_status`` field; only genuine failures (bad symbol, no data,
internal crash) return HTTP error codes.

No stack traces or internal details are ever sent to the client.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path

from app.schemas import MarketForecastResponse
from app.services import market_ml

log = logging.getLogger(__name__)

router = APIRouter(prefix="/market-ml", tags=["market-ml"])


@router.get("/{symbol}/forecast", response_model=MarketForecastResponse)
async def forecast(
    symbol: str = Path(..., min_length=1, max_length=20),
) -> MarketForecastResponse:
    """Return short-term directional forecasts for *symbol* across four horizons.

    The disclaimer field is always present in the response and must be shown
    to the learner.  When no model has been trained yet, all horizons carry
    ``model_status="not_trained"`` — this is a valid 200 response, not an error.

    Possible HTTP error codes:

    * **400** — symbol is syntactically invalid (empty or > 20 chars; caught by
      FastAPI path validation) or cannot be normalised by the market service.
    * **404** — symbol is valid but has no OHLCV data available.
    * **500** — unexpected internal error; details are logged server-side only.
    """
    try:
        return market_ml.get_forecast(symbol)
    except ValueError as exc:
        # normalize_symbol raises ValueError for truly unparseable input.
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {exc}") from exc
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"No market data available for {symbol!r}.",
        )
    except Exception:
        log.exception("Unhandled error in forecast endpoint for symbol=%r", symbol)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        )
