"""Endpoints de visibilidad del book PAPER; no contienen paths de ejecución."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.paper_positions import (
    PaperPositionUnavailable,
    read_paper_positions,
)

router = APIRouter(prefix="/api/paper", tags=["paper"])


class PaperPositionResponse(BaseModel):
    symbol: str
    open_quantity: str
    cost_basis_open_usdt: str
    mark_price: str
    market_value_usdt: str
    unrealized_pnl_usdt: str


class PaperPositionsResponse(BaseModel):
    mode: str = "paper"
    source: str = "paper_ledger_transactional"
    as_of: datetime
    positions: list[PaperPositionResponse]
    total_count: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/positions", response_model=PaperPositionsResponse)
def get_paper_positions(db: Session = Depends(get_db)) -> PaperPositionsResponse:
    """Posiciones paper valoradas desde SoT; 503 si falta al menos un mark."""
    try:
        positions = read_paper_positions(db)
    except PaperPositionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PaperPositionsResponse(
        as_of=datetime.now(timezone.utc),
        positions=[PaperPositionResponse(**position.to_dict()) for position in positions],
        total_count=len(positions),
    )
