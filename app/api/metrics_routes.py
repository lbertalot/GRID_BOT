"""
Metrics API Routes - Endpoints para métricas de rendimiento avanzadas
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import logging

from app.services.performance_analyzer import performance_analyzer, PerformanceMetrics

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


# Pydantic models for API
class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics"""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    current_balance: float
    initial_balance: float
    period_days: int


class AssetPerformanceResponse(BaseModel):
    """Response model for asset performance"""
    symbol: str
    initial_price: float
    final_price: float
    price_change_percent: float
    volatility_annualized: float
    avg_volume: float
    days_analyzed: int
    current_price: float


class PortfolioAllocationResponse(BaseModel):
    """Response model for portfolio allocation"""
    allocation: Dict[str, Dict]
    total_value: float
    assets_count: int


# Performance metrics endpoint
@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    days: int = Query(30, ge=1, le=365, description="Número de días para el análisis")
):
    """
    Obtiene métricas comprehensivas de rendimiento
    
    Args:
        days: Número de días para el análisis (1-365)
    
    Returns:
        Métricas de rendimiento incluyendo Sharpe Ratio, drawdown, etc.
    """
    try:
        logger.info(f"Obteniendo métricas de rendimiento para {days} días")
        
        metrics = await performance_analyzer.calculate_comprehensive_metrics(days)
        
        return PerformanceMetricsResponse(
            total_return=metrics.total_return,
            sharpe_ratio=metrics.sharpe_ratio,
            max_drawdown=metrics.max_drawdown,
            volatility=metrics.volatility,
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor,
            total_trades=metrics.total_trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            avg_win=metrics.avg_win,
            avg_loss=metrics.avg_loss,
            best_trade=metrics.best_trade,
            worst_trade=metrics.worst_trade,
            current_balance=metrics.current_balance,
            initial_balance=metrics.initial_balance,
            period_days=metrics.period_days
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas de rendimiento: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas: {str(e)}")


# Asset performance endpoint
@router.get("/asset/{symbol}", response_model=AssetPerformanceResponse)
async def get_asset_performance(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Número de días para el análisis")
):
    """
    Obtiene el rendimiento de un activo específico
    
    Args:
        symbol: Símbolo del activo (ej: BNBUSDT)
        days: Número de días para el análisis
    
    Returns:
        Métricas de rendimiento del activo
    """
    try:
        logger.info(f"Obteniendo rendimiento de {symbol} para {days} días")
        
        performance = await performance_analyzer.get_asset_performance(symbol, days)
        
        if "error" in performance:
            raise HTTPException(status_code=400, detail=performance["error"])
        
        return AssetPerformanceResponse(**performance)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo rendimiento de {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo rendimiento: {str(e)}")


# Portfolio allocation endpoint
@router.get("/allocation", response_model=PortfolioAllocationResponse)
async def get_portfolio_allocation():
    """
    Obtiene la distribución actual del portafolio
    
    Returns:
        Distribución del portafolio por activo
    """
    try:
        logger.info("Obteniendo distribución del portafolio")
        
        allocation = await performance_analyzer.get_portfolio_allocation()
        
        if "error" in allocation:
            raise HTTPException(status_code=500, detail=allocation["error"])
        
        return PortfolioAllocationResponse(**allocation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo distribución del portafolio: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo distribución: {str(e)}")


# Current portfolio value endpoint
@router.get("/portfolio/value")
async def get_current_portfolio_value():
    """
    Obtiene el valor actual del portafolio
    
    Returns:
        Valor total del portafolio en USDT
    """
    try:
        logger.info("Obteniendo valor actual del portafolio")
        
        value = await performance_analyzer.get_current_portfolio_value()
        
        return {
            "current_value": value,
            "currency": "USDT",
            "timestamp": "2025-07-26T17:40:00Z"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo valor del portafolio: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo valor: {str(e)}")


# Risk metrics endpoint
@router.get("/risk")
async def get_risk_metrics(
    days: int = Query(30, ge=1, le=365, description="Número de días para el análisis")
):
    """
    Obtiene métricas de riesgo específicas
    
    Args:
        days: Número de días para el análisis
    
    Returns:
        Métricas de riesgo (VaR, CVaR, etc.)
    """
    try:
        logger.info(f"Obteniendo métricas de riesgo para {days} días")
        
        metrics = await performance_analyzer.calculate_comprehensive_metrics(days)
        
        # Calcular métricas de riesgo adicionales
        risk_metrics = {
            "max_drawdown": metrics.max_drawdown,
            "volatility": metrics.volatility,
            "sharpe_ratio": metrics.sharpe_ratio,
            "win_rate": metrics.win_rate,
            "profit_factor": metrics.profit_factor,
            "risk_reward_ratio": abs(metrics.avg_win / metrics.avg_loss) if metrics.avg_loss != 0 else 0,
            "consecutive_losses": 0,  # Se calcularía con datos históricos reales
            "largest_loss": abs(metrics.worst_trade),
            "largest_win": metrics.best_trade,
            "avg_trade_duration": 0,  # Se calcularía con datos históricos reales
            "period_days": days
        }
        
        return risk_metrics
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas de riesgo: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas de riesgo: {str(e)}")


# Trading statistics endpoint
@router.get("/trading/stats")
async def get_trading_statistics(
    days: int = Query(30, ge=1, le=365, description="Número de días para el análisis")
):
    """
    Obtiene estadísticas detalladas de trading
    
    Args:
        days: Número de días para el análisis
    
    Returns:
        Estadísticas detalladas de trading
    """
    try:
        logger.info(f"Obteniendo estadísticas de trading para {days} días")
        
        metrics = await performance_analyzer.calculate_comprehensive_metrics(days)
        
        trading_stats = {
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": metrics.win_rate,
            "avg_win": metrics.avg_win,
            "avg_loss": metrics.avg_loss,
            "best_trade": metrics.best_trade,
            "worst_trade": metrics.worst_trade,
            "profit_factor": metrics.profit_factor,
            "total_pnl": metrics.avg_win * metrics.winning_trades + metrics.avg_loss * metrics.losing_trades,
            "net_pnl": metrics.avg_win * metrics.winning_trades + metrics.avg_loss * metrics.losing_trades,
            "period_days": days,
            "trades_per_day": metrics.total_trades / days if days > 0 else 0
        }
        
        return trading_stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de trading: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")


# Health check for metrics
@router.get("/health")
async def metrics_health_check():
    """
    Health check para el servicio de métricas
    
    Returns:
        Estado del servicio de métricas
    """
    try:
        # Verificar que podemos obtener el valor del portafolio
        value = await performance_analyzer.get_current_portfolio_value()
        
        return {
            "status": "healthy",
            "service": "performance-metrics",
            "portfolio_value": value,
            "timestamp": "2025-07-26T17:40:00Z"
        }
        
    except Exception as e:
        logger.error(f"Error en health check de métricas: {e}")
        return {
            "status": "unhealthy",
            "service": "performance-metrics",
            "error": str(e),
            "timestamp": "2025-07-26T17:40:00Z"
        } 