from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
import os

from app.core.auth import require_auth
from app.schemas.transaction_cost_audit import (
    TransactionCostAuditRequest,
    TransactionCostAuditResponse,
)
from app.services.binance_service import BinanceService
from app.services.transaction_cost_audit_service import (
    run_transaction_cost_audit_for_api,
)


router = APIRouter(prefix="/api/simulations", tags=["simulations"])


class DryRunRequest(BaseModel):
    symbol: str = Field(..., description="Símbolo, ej: BTCUSDT")
    side: Literal["BUY", "SELL"] = "BUY"
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)


@router.post("/dry-run")
def dry_run(
    req: DryRunRequest = Body(...), api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    # Forzar PAPER_TRADING para seguridad
    os.environ["PAPER_TRADING"] = "true"
    svc = BinanceService()
    # Forzar simulación incluso si settings.paper_trading fue cargado antes
    svc.simulation_mode = True

    try:
        validation = svc.validate_order_parameters(
            req.symbol.upper(), req.quantity, side=req.side, order_type=req.order_type
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error validando parámetros: {e}")

    if not validation.get("is_valid"):
        return {
            "success": False,
            "message": "Validation failed",
            "validation": validation,
        }

    try:
        order = svc.execute_trading_order(
            req.symbol.upper(),
            req.side,
            req.order_type,
            validation["recommended_quantity"],
            req.price,
        )
        return {
            "success": True,
            "mode": "PAPER",
            "validation": validation,
            "order": order,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error simulando orden: {e}")


@router.post(
    "/transaction-cost-audit",
    response_model=TransactionCostAuditResponse,
    summary="Auditoría after-cost (comisión + spread + slippage)",
    description=(
        "Calcula fricción total en quote (USDT) sobre un notional dado, alineado al "
        "modelo `transaction_cost_model` y al backtest. Requiere auth; no ejecuta órdenes."
    ),
)
def transaction_cost_audit(
    body: TransactionCostAuditRequest = Body(...),
    _api_key: str = Depends(require_auth),
) -> TransactionCostAuditResponse:
    try:
        return run_transaction_cost_audit_for_api(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
