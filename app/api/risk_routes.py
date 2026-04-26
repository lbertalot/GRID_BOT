#!/usr/bin/env python3
"""
Endpoints para el RiskManager evolucionado.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from datetime import datetime

from app.core.risk_manager import RiskManager, MarketRegime
from app.services.hybrid_ml_engine import HybridMLEngine
from app.services.strategy_selector import StrategySelector

router = APIRouter(prefix="/api/v2/risk", tags=["risk"])


# Dependencias
def get_risk_manager() -> RiskManager:
    """Obtiene instancia del RiskManager."""
    # TODO: Implementar inyección de dependencias real
    return RiskManager()


def get_ml_engine() -> HybridMLEngine:
    """Obtiene instancia del HybridMLEngine."""
    # TODO: Implementar inyección de dependencias real
    return HybridMLEngine()


def get_strategy_selector(
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> StrategySelector:
    """Obtiene instancia del StrategySelector."""
    # TODO: Implementar inyección de dependencias real
    return StrategySelector(risk_manager)


@router.get("/status")
async def get_risk_status(
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Obtiene el estado actual del riesgo.

    Returns:
        Estado del riesgo incluyendo exposición, pérdidas, breaker state, etc.
    """
    try:
        status = risk_manager.get_risk_status()
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting risk status: {str(e)}"
        )


@router.post("/emergency-stop")
async def trigger_emergency_stop(
    reason: str, risk_manager: RiskManager = Depends(get_risk_manager)
) -> Dict[str, Any]:
    """
    Activa el stop de emergencia.

    Args:
        reason: Razón del stop de emergencia

    Returns:
        Confirmación del stop de emergencia
    """
    try:
        risk_manager.trigger_emergency_stop(reason)
        return {
            "success": True,
            "message": f"Emergency stop triggered: {reason}",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error triggering emergency stop: {str(e)}"
        )


@router.post("/reset-emergency-stop")
async def reset_emergency_stop(
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Resetea el stop de emergencia.

    Returns:
        Confirmación del reset
    """
    try:
        risk_manager.reset_emergency_stop()
        return {
            "success": True,
            "message": "Emergency stop reset successfully",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error resetting emergency stop: {str(e)}"
        )


@router.post("/update-metrics")
async def update_risk_metrics(
    daily_loss: float,
    total_exposure: float,
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Actualiza métricas de riesgo.

    Args:
        daily_loss: Pérdida diaria en porcentaje
        total_exposure: Exposición total en porcentaje

    Returns:
        Confirmación de actualización
    """
    try:
        risk_manager.update_metrics(daily_loss, total_exposure)
        return {
            "success": True,
            "message": "Risk metrics updated successfully",
            "data": {"daily_loss": daily_loss, "total_exposure": total_exposure},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating risk metrics: {str(e)}"
        )


@router.post("/apply-regime-filter")
async def apply_market_regime_filter(
    regime: MarketRegime, risk_manager: RiskManager = Depends(get_risk_manager)
) -> Dict[str, Any]:
    """
    Aplica filtro de régimen de mercado.

    Args:
        regime: Régimen de mercado a aplicar

    Returns:
        Confirmación de aplicación del filtro
    """
    try:
        risk_manager.apply_market_regime_filter(regime)
        return {
            "success": True,
            "message": f"Market regime filter applied: {regime.value}",
            "data": {
                "regime": regime.value,
                "max_exposure_pct": risk_manager.max_total_exposure_pct,
                "min_profit_bps": risk_manager.min_profit_bps,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error applying regime filter: {str(e)}"
        )


@router.get("/circuit-breaker-status")
async def get_circuit_breaker_status(
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Obtiene el estado del circuit breaker.

    Returns:
        Estado del circuit breaker
    """
    try:
        breaker_state = risk_manager.check_circuit_breaker()
        return {
            "success": True,
            "data": {
                "breaker_state": breaker_state.value,
                "emergency_stop": risk_manager.emergency_stop,
                "current_regime": risk_manager.current_regime.value,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting circuit breaker status: {str(e)}"
        )


@router.post("/calculate-position-size")
async def calculate_position_size(
    symbol: str,
    account_equity: float,
    atr: float,
    winrate_estimate: float,
    avg_win_loss_ratio: float,
    price: float,
    risk_per_trade_pct: float = 0.02,
    cap_symbol_pct: float = 0.20,
    cap_equity_pct: float = 0.80,
    cap_daily_loss_pct: float = 0.05,
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Calcula tamaño de posición dinámico usando Kelly fraccional.

    Args:
        symbol: Símbolo del trading pair
        account_equity: Equity de la cuenta
        atr: Average True Range
        winrate_estimate: Estimación de winrate
        avg_win_loss_ratio: Ratio promedio ganancia/pérdida
        price: Precio actual
        risk_per_trade_pct: Porcentaje de riesgo por trade
        cap_symbol_pct: Límite por símbolo
        cap_equity_pct: Límite por equity
        cap_daily_loss_pct: Límite por pérdida diaria

    Returns:
        Tamaño de posición calculado
    """
    try:
        from app.core.risk_manager import PositionSizeParams

        params = PositionSizeParams(
            symbol=symbol,
            account_equity=account_equity,
            atr=atr,
            winrate_estimate=winrate_estimate,
            avg_win_loss_ratio=avg_win_loss_ratio,
            price=price,
            risk_per_trade_pct=risk_per_trade_pct,
            cap_symbol_pct=cap_symbol_pct,
            cap_equity_pct=cap_equity_pct,
            cap_daily_loss_pct=cap_daily_loss_pct,
        )

        position_size = risk_manager.calculate_dynamic_position_size(params)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "position_size_usdt": position_size,
                "position_size_pct": position_size / account_equity,
                "params": {
                    "account_equity": account_equity,
                    "atr": atr,
                    "winrate_estimate": winrate_estimate,
                    "avg_win_loss_ratio": avg_win_loss_ratio,
                    "price": price,
                },
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating position size: {str(e)}"
        )


@router.post("/calculate-trailing-stop")
async def calculate_trailing_stop(
    symbol: str,
    entry_price: float,
    atr: float,
    multiplier_atr: float = 2.0,
    is_long: bool = True,
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Calcula trailing stop adaptativo basado en ATR.

    Args:
        symbol: Símbolo del trading pair
        entry_price: Precio de entrada
        atr: Average True Range
        multiplier_atr: Multiplicador ATR
        is_long: Si es posición larga

    Returns:
        Precio del stop loss
    """
    try:
        from app.core.risk_manager import TrailingStopParams

        params = TrailingStopParams(
            symbol=symbol,
            entry_price=entry_price,
            atr=atr,
            multiplier_atr=multiplier_atr,
            is_long=is_long,
        )

        stop_price = risk_manager.get_adaptive_trailing_stop(params)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "atr": atr,
                "multiplier_atr": multiplier_atr,
                "is_long": is_long,
                "distance_pct": abs(stop_price - entry_price) / entry_price,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating trailing stop: {str(e)}"
        )


@router.post("/update-trailing-stop")
async def update_trailing_stop(
    symbol: str,
    current_price: float,
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Actualiza trailing stop con el precio actual.

    Args:
        symbol: Símbolo del trading pair
        current_price: Precio actual

    Returns:
        Nuevo precio de stop loss (si se actualizó)
    """
    try:
        new_stop = risk_manager.update_trailing_stop(symbol, current_price)

        if new_stop is not None:
            return {
                "success": True,
                "data": {
                    "symbol": symbol,
                    "new_stop_price": new_stop,
                    "current_price": current_price,
                    "updated": True,
                },
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "success": True,
                "data": {
                    "symbol": symbol,
                    "current_price": current_price,
                    "updated": False,
                    "message": "No trailing stop update needed",
                },
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating trailing stop: {str(e)}"
        )


@router.get("/trailing-stops")
async def get_trailing_stops(
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """
    Obtiene todos los trailing stops activos.

    Returns:
        Lista de trailing stops activos
    """
    try:
        trailing_stops = risk_manager.trailing_stops

        return {
            "success": True,
            "data": {"trailing_stops": trailing_stops, "count": len(trailing_stops)},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting trailing stops: {str(e)}"
        )
