"""
Esquemas Pydantic para endpoints de portfolio y posiciones
"""

from pydantic import BaseModel
from typing import List, Optional


class AssetSummary(BaseModel):
    """Resumen de un activo en el portfolio"""

    asset: str
    free: float
    locked: float
    total_usdt_value: float


class PortfolioSummary(BaseModel):
    """Resumen completo del portfolio"""

    cash_usdt: float
    portfolio_total_usdt: float
    assets: List[AssetSummary]


class Position(BaseModel):
    """Posición abierta en el trading"""

    symbol: str
    quantity: float
    entry_price: float
    side: str
    unrealized_pnl: Optional[float] = None
    timestamp: Optional[str] = None


class PositionsResponse(BaseModel):
    """Respuesta del endpoint de posiciones"""

    positions: List[Position]
    total_count: int
