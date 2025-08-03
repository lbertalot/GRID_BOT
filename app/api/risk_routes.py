#!/usr/bin/env python3
"""
API Routes para Gestión de Riesgos
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.services.risk_manager import risk_manager, RiskLevel, RiskStatus
# from app.core.auth import get_current_user  # Comentado temporalmente

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Management"])

class RiskStatusResponse(BaseModel):
    """Respuesta del estado de riesgo"""
    status: str
    trading_enabled: bool
    emergency_stop: bool
    metrics: Dict
    limits: Dict
    last_updated: str

class EmergencyStopRequest(BaseModel):
    """Request para activar/desactivar parada de emergencia"""
    enabled: bool
    reason: Optional[str] = None

class RiskAlertResponse(BaseModel):
    """Respuesta de alerta de riesgo"""
    level: str
    message: str
    timestamp: str
    action_required: bool

class AssetRiskResponse(BaseModel):
    """Respuesta de riesgo por activo"""
    symbol: str
    status: str
    exposure: float
    position_value: float
    risk_level: str

@router.get("/status", response_model=RiskStatusResponse)
async def get_risk_status():
    """Obtiene el estado actual del sistema de gestión de riesgos"""
    try:
        status_data = await risk_manager.get_risk_status()
        return RiskStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado de riesgo: {str(e)}")

@router.post("/emergency-stop")
async def set_emergency_stop(request: EmergencyStopRequest):
    """Activa o desactiva la parada de emergencia"""
    try:
        await risk_manager.set_emergency_stop(request.enabled)
        
        action = "activada" if request.enabled else "desactivada"
        message = f"Parada de emergencia {action}"
        if request.reason:
            message += f" - Razón: {request.reason}"
        
        return {
            "status": "success",
            "message": message,
            "emergency_stop": request.enabled,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error configurando parada de emergencia: {str(e)}")

@router.get("/portfolio/check")
async def check_portfolio_risk():
    """Verifica el riesgo del portafolio completo"""
    try:
        risk_status = await risk_manager.check_portfolio_risk()
        risk_metrics = await risk_manager.calculate_risk_metrics()
        
        return {
            "status": risk_status.value,
            "risk_level": "critical" if risk_status == RiskStatus.STOP_TRADING else 
                         "high" if risk_status == RiskStatus.DANGER else
                         "medium" if risk_status == RiskStatus.WARNING else "low",
            "metrics": {
                "total_exposure": f"{risk_metrics.total_exposure:.2%}",
                "current_daily_loss": f"{risk_metrics.current_daily_loss:.2%}",
                "largest_position": f"{risk_metrics.largest_position:.2%}",
                "portfolio_volatility": f"{risk_metrics.portfolio_volatility:.2%}",
                "sharpe_ratio": f"{risk_metrics.sharpe_ratio:.2f}",
                "max_drawdown": f"{risk_metrics.max_drawdown:.2%}",
                "risk_score": f"{risk_metrics.risk_score:.2f}"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verificando riesgo del portafolio: {str(e)}")

@router.get("/asset/{symbol}", response_model=AssetRiskResponse)
async def check_asset_risk(symbol: str):
    """Verifica el riesgo de un activo específico"""
    try:
        risk_status = await risk_manager.check_asset_risk(symbol)
        position = risk_manager._get_asset_position(symbol)
        
        return AssetRiskResponse(
            symbol=symbol,
            status=risk_status.value,
            exposure=position['value'] if position else 0.0,
            position_value=position['value'] if position else 0.0,
            risk_level="critical" if risk_status == RiskStatus.STOP_TRADING else 
                      "high" if risk_status == RiskStatus.DANGER else
                      "medium" if risk_status == RiskStatus.WARNING else "low"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verificando riesgo del activo {symbol}: {str(e)}")

@router.post("/stop-loss/{symbol}")
async def execute_stop_loss(symbol: str):
    """Ejecuta stop-loss para un activo específico"""
    try:
        success = await risk_manager.execute_stop_loss(symbol)
        
        if success:
            return {
                "status": "success",
                "message": f"Stop-loss ejecutado exitosamente para {symbol}",
                "symbol": symbol,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": f"No se pudo ejecutar stop-loss para {symbol}",
                "symbol": symbol,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando stop-loss para {symbol}: {str(e)}")

@router.get("/metrics")
async def get_risk_metrics():
    """Obtiene métricas detalladas de riesgo"""
    try:
        risk_metrics = await risk_manager.calculate_risk_metrics()
        
        return {
            "total_exposure": f"{risk_metrics.total_exposure:.2%}",
            "current_daily_loss": f"{risk_metrics.current_daily_loss:.2%}",
            "largest_position": f"{risk_metrics.largest_position:.2%}",
            "portfolio_volatility": f"{risk_metrics.portfolio_volatility:.2%}",
            "sharpe_ratio": f"{risk_metrics.sharpe_ratio:.2f}",
            "max_drawdown": f"{risk_metrics.max_drawdown:.2%}",
            "risk_score": f"{risk_metrics.risk_score:.2f}",
            "limits": {
                "max_daily_loss": f"{risk_manager.max_daily_loss_percentage:.2%}",
                "max_position_size": f"{risk_manager.max_position_size_percentage:.2%}",
                "max_total_exposure": f"{risk_manager.max_total_exposure_percentage:.2%}",
                "stop_loss_percentage": f"{risk_manager.stop_loss_percentage:.2%}",
                "max_drawdown": f"{risk_manager.max_drawdown_percentage:.2%}"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas de riesgo: {str(e)}")

@router.get("/alerts")
async def get_recent_alerts():
    """Obtiene alertas de riesgo recientes"""
    try:
        # Obtener las últimas alertas (simulado)
        alerts = []
        for alert_key, timestamp in list(risk_manager.last_alerts.items())[-10:]:
            level, message = alert_key.split("_", 1)
            alerts.append({
                "level": level,
                "message": message[:100] + "..." if len(message) > 100 else message,
                "timestamp": timestamp.isoformat(),
                "action_required": level in ["critical", "high"]
            })
        
        return {
            "alerts": alerts,
            "total_alerts": len(alerts),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo alertas: {str(e)}")

@router.get("/health")
async def risk_health_check():
    """Health check del sistema de gestión de riesgos"""
    try:
        # Verificar que el RiskManager esté funcionando
        status = await risk_manager.get_risk_status()
        
        return {
            "status": "healthy",
            "risk_manager": "operational",
            "trading_enabled": risk_manager.trading_enabled,
            "emergency_stop": risk_manager.emergency_stop,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        } 