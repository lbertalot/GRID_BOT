"""
Endpoints para gestión de comisiones y validaciones de rentabilidad
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.services.commission_manager import commission_manager
from app.services.binance_service import BinanceService
from app.core.auth import require_auth

router = APIRouter(prefix="/api/v1/commissions", tags=["Commissions"])

class CommissionValidationRequest(BaseModel):
    symbol: str = Field(..., description="Símbolo del par (ej: BTCUSDT)")
    quantity: float = Field(..., gt=0, description="Cantidad a operar")
    price: float = Field(..., gt=0, description="Precio por unidad")
    side: str = Field(..., description="Lado de la operación (BUY/SELL)")
    order_type: str = Field(default="MARKET", description="Tipo de orden")

class GridProfitabilityRequest(BaseModel):
    symbol: str = Field(..., description="Símbolo del par")
    min_price: float = Field(..., gt=0, description="Precio mínimo del grid")
    max_price: float = Field(..., gt=0, description="Precio máximo del grid")
    quantity: float = Field(..., gt=0, description="Cantidad por nivel")
    num_levels: int = Field(..., ge=2, le=100, description="Número de niveles")
    min_profit_percentage: float = Field(default=0.5, ge=0.1, le=10.0, description="Porcentaje mínimo de ganancia")

@router.get("/rates")
async def get_commission_rates(
    symbol: Optional[str] = None,
    api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Obtener tasas de comisión actuales
    """
    try:
        rates = commission_manager.get_commission_rates(symbol)
        return {
            "status": "success",
            "symbol": symbol,
            "rates": rates,
            "default_maker": commission_manager.default_maker_commission,
            "default_taker": commission_manager.default_taker_commission
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo tasas de comisión: {str(e)}")

@router.post("/calculate")
async def calculate_commission(
    request: CommissionValidationRequest,
    api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Calcular comisión para una operación específica
    """
    try:
        notional_value = request.quantity * request.price
        commission = commission_manager.calculate_commission(
            notional_value, request.order_type, request.symbol
        )
        
        return {
            "status": "success",
            "symbol": request.symbol,
            "side": request.side,
            "quantity": request.quantity,
            "price": request.price,
            "notional_value": notional_value,
            "commission_usdt": commission,
            "commission_percentage": (commission / notional_value * 100) if notional_value > 0 else 0,
            "order_type": request.order_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando comisión: {str(e)}")

@router.post("/validate-profitability")
async def validate_grid_profitability(
    request: GridProfitabilityRequest,
    api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Validar rentabilidad de una estrategia de grid trading considerando comisiones
    """
    try:
        binance_service = BinanceService()
        analysis = binance_service.validate_grid_profitability(
            request.symbol,
            request.min_price,
            request.max_price,
            request.quantity,
            request.num_levels,
            request.min_profit_percentage
        )
        
        return {
            "status": "success",
            "analysis": analysis,
            "request": request.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validando rentabilidad: {str(e)}")

@router.post("/calculate-profit")
async def calculate_profit_with_commissions(
    symbol: str,
    buy_price: float,
    sell_price: float,
    quantity: float,
    buy_order_type: str = "MARKET",
    sell_order_type: str = "MARKET",
    api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Calcular ganancia/pérdida considerando comisiones
    """
    try:
        profit_data = commission_manager.calculate_profit_with_commissions(
            buy_price, sell_price, quantity, buy_order_type, sell_order_type, symbol
        )
        
        return {
            "status": "success",
            "symbol": symbol,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "quantity": quantity,
            "profit_analysis": profit_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando ganancia: {str(e)}")

@router.get("/update-rates")
async def update_commission_rates(
    api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Actualizar tasas de comisión desde Binance
    """
    try:
        commission_manager._update_commission_rates()
        
        return {
            "status": "success",
            "message": "Tasas de comisión actualizadas",
            "current_rates": {
                "maker": commission_manager.default_maker_commission,
                "taker": commission_manager.default_taker_commission
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando tasas: {str(e)}")

@router.get("/status")
async def get_commission_status(
    api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Obtener estado del sistema de comisiones
    """
    try:
        return {
            "status": "success",
            "commission_manager_initialized": commission_manager.client is not None,
            "default_rates": {
                "maker": commission_manager.default_maker_commission,
                "taker": commission_manager.default_taker_commission
            },
            "cache_size": len(commission_manager._commission_cache),
            "symbol_cache_size": len(commission_manager._symbol_info_cache)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado: {str(e)}")
