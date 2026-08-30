"""Stock catalogue + simple search."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Stock

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/stocks")
def list_stocks(
    q: str | None = Query(None, description="Search across name and symbol"),
    sector: str | None = None,
    db: Session = Depends(get_db),
):
    qy = db.query(Stock)
    if sector:
        qy = qy.filter(Stock.sector == sector)
    if q:
        like = f"%{q.upper()}%"
        qy = qy.filter((Stock.name.ilike(like)) | (Stock.symbol.ilike(like)))
    rows = qy.order_by(Stock.name).all()
    return [
        {
            "symbol": s.symbol,
            "name": s.name,
            "sector": s.sector,
            "market_cap_band": s.market_cap_band,
            "risk_level": s.risk_level,
        }
        for s in rows
    ]


@router.get("/sectors")
def list_sectors(db: Session = Depends(get_db)):
    rows = db.query(Stock.sector).distinct().all()
    return sorted({r[0] for r in rows})
