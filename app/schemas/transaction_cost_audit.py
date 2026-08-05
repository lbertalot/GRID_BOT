"""
Esquemas HTTP para auditoría after-cost (protocolo §3.4).

Request/response tipados para FastAPI; montos en quote como Decimal en entrada,
strings en salida para serialización JSON estable.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionCostAuditRequest(BaseModel):
    """Entrada para cálculo auditable de fricción sobre notional quote (p. ej. USDT)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    notional_quote: Decimal = Field(..., gt=0, description="Notional en moneda quote")
    side: Literal["BUY", "SELL"] = Field(default="BUY")
    order_type: Literal["MARKET", "LIMIT"] = Field(default="MARKET")
    spread_bps: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=Decimal("10000"),
        description="Spread modelado en puntos básicos",
    )
    slippage_bps: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=Decimal("10000"),
        description="Slippage modelado en puntos básicos",
    )
    commission_maker_fraction: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=1,
        description="Si se omite, usa valor por defecto del exchange en código",
    )
    commission_taker_fraction: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=1,
        description="Si se omite, usa valor por defecto del exchange en código",
    )


class TransactionCostAuditResponse(BaseModel):
    """Salida alineada a TransactionCostAudit.to_serializable_dict()."""

    model_config = ConfigDict(extra="forbid")

    notional_quote: str
    side: str
    order_type: str
    spread_bps: str
    slippage_bps: str
    commission_usdt: str
    spread_cost_usdt: str
    slippage_cost_usdt: str
    total_friction_usdt: str
