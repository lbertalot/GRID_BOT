#!/usr/bin/env python3
"""
API Routes para Optimización de Configuración
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
import numpy as np

from app.services.config_manager import config_manager, OptimizationRequest, OptimizationStrategy

router = APIRouter(prefix="/api/v1/config", tags=["Configuration Optimization"])

class OptimizationResponse(BaseModel):
    """Respuesta de optimización"""
    symbol: str
    min_price: float
    max_price: float
    grids: int
    quantity: float
    confidence_score: float
    optimization_strategy: str
    timestamp: str
    backtest_results: Optional[Dict] = None

class MarketAnalysisResponse(BaseModel):
    """Respuesta de análisis de mercado"""
    symbol: str
    current_price: float
    volatility: Dict
    volume_24h: float
    price_change_24h: float
    trend: str
    high_24h: float
    low_24h: float
    timestamp: str

class OptimizationHistoryResponse(BaseModel):
    """Respuesta de historial de optimizaciones"""
    symbol: str
    optimizations: List[Dict]

@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_configuration(request: OptimizationRequest):
    """Optimiza parámetros de configuración automáticamente"""
    try:
        optimized_config = await config_manager.optimize_parameters(request)
        
        return OptimizationResponse(
            symbol=optimized_config.symbol,
            min_price=optimized_config.min_price,
            max_price=optimized_config.max_price,
            grids=optimized_config.grids,
            quantity=optimized_config.quantity,
            confidence_score=optimized_config.confidence_score,
            optimization_strategy=optimized_config.optimization_strategy,
            timestamp=optimized_config.timestamp.isoformat(),
            backtest_results=optimized_config.backtest_results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizando configuración: {str(e)}")

@router.get("/market-analysis/{symbol}", response_model=MarketAnalysisResponse)
async def get_market_analysis(symbol: str):
    """Obtiene análisis detallado de mercado para un símbolo"""
    try:
        market_data = await config_manager._get_market_data(symbol)
        
        # Determinar nivel de volatilidad
        volatility_level = "Baja"
        if market_data.volatility > 0.1:
            volatility_level = "Alta"
        elif market_data.volatility > 0.05:
            volatility_level = "Media"
        
        # Determinar tendencia
        trend = "Lateral"
        if market_data.price_change_24h > 2:
            trend = "Alcista Fuerte"
        elif market_data.price_change_24h > 0.5:
            trend = "Alcista"
        elif market_data.price_change_24h < -2:
            trend = "Bajista Fuerte"
        elif market_data.price_change_24h < -0.5:
            trend = "Bajista"
        
        return MarketAnalysisResponse(
            symbol=symbol,
            current_price=market_data.current_price,
            volatility={
                "value": market_data.volatility,
                "level": volatility_level,
                "description": f"Volatilidad {volatility_level.lower()} - {market_data.volatility:.2%}"
            },
            volume_24h=market_data.volume_24h,
            price_change_24h=market_data.price_change_24h,
            trend=trend,
            high_24h=market_data.high_24h,
            low_24h=market_data.low_24h,
            timestamp=market_data.timestamp.isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo análisis de mercado para {symbol}: {str(e)}")

@router.get("/market-analysis/{symbol}/detailed")
async def get_detailed_market_analysis(symbol: str):
    """Obtiene análisis de mercado muy detallado con recomendaciones"""
    try:
        market_data = await config_manager._get_market_data(symbol)
        
        # Obtener datos históricos para análisis más profundo
        historical_data = await config_manager._get_historical_data(symbol, days=30)
        
        # Calcular métricas adicionales
        if historical_data:
            prices = [d['close'] for d in historical_data]
            returns = np.diff(np.log(prices))
            
            # Calcular métricas estadísticas
            avg_return = np.mean(returns)
            volatility_annualized = np.std(returns) * np.sqrt(365)
            sharpe_ratio = avg_return / (np.std(returns) + 1e-8) if len(returns) > 1 else 0.0
            
            # Calcular máximo drawdown
            cumulative_returns = np.cumprod(1 + returns)
            peak = cumulative_returns[0]
            max_dd = 0.0
            for cr in cumulative_returns:
                if cr > peak:
                    peak = cr
                dd = (peak - cr) / peak
                max_dd = max(max_dd, dd)
        else:
            avg_return = 0.0
            volatility_annualized = market_data.volatility
            sharpe_ratio = 0.0
            max_dd = 0.0
        
        # Generar recomendaciones
        recommendations = []
        
        if market_data.volatility > 0.15:
            recommendations.append("Alta volatilidad - Considerar estrategias conservadoras")
        elif market_data.volatility < 0.05:
            recommendations.append("Baja volatilidad - Estrategias agresivas pueden ser efectivas")
        
        if market_data.volume_24h > 1000000:
            recommendations.append("Alto volumen - Buena liquidez para trading")
        elif market_data.volume_24h < 100000:
            recommendations.append("Bajo volumen - Cuidado con la liquidez")
        
        if sharpe_ratio > 1.0:
            recommendations.append("Sharpe ratio positivo - Buena relación riesgo/retorno")
        elif sharpe_ratio < 0:
            recommendations.append("Sharpe ratio negativo - Alto riesgo")
        
        if max_dd > 0.2:
            recommendations.append("Alto drawdown histórico - Gestión de riesgo crítica")
        
        # Recomendación de estrategia
        if market_data.volatility > 0.1 and market_data.volume_24h > 500000:
            recommended_strategy = "VOLATILITY_BASED"
        elif market_data.volume_24h > 1000000:
            recommended_strategy = "VOLUME_BASED"
        elif len(historical_data) > 20:
            recommended_strategy = "MACHINE_LEARNING"
        else:
            recommended_strategy = "GRID_OPTIMIZATION"
        
        return {
            "symbol": symbol,
            "current_price": market_data.current_price,
            "volatility": {
                "daily": market_data.volatility,
                "annualized": volatility_annualized,
                "level": "Alta" if market_data.volatility > 0.1 else "Media" if market_data.volatility > 0.05 else "Baja"
            },
            "volume_analysis": {
                "volume_24h": market_data.volume_24h,
                "volume_level": "Alto" if market_data.volume_24h > 1000000 else "Medio" if market_data.volume_24h > 100000 else "Bajo",
                "liquidity_score": min(market_data.volume_24h / 1000000, 1.0)
            },
            "price_analysis": {
                "change_24h": market_data.price_change_24h,
                "high_24h": market_data.high_24h,
                "low_24h": market_data.low_24h,
                "trend": "Alcista" if market_data.price_change_24h > 0 else "Bajista" if market_data.price_change_24h < 0 else "Lateral"
            },
            "risk_metrics": {
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_dd,
                "avg_return": avg_return,
                "risk_level": "Alto" if max_dd > 0.2 or sharpe_ratio < 0 else "Medio" if max_dd > 0.1 else "Bajo"
            },
            "recommendations": recommendations,
            "recommended_strategy": recommended_strategy,
            "strategy_reason": f"Recomendado basado en volatilidad {market_data.volatility:.2%} y volumen ${market_data.volume_24h/1000000:.1f}M",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo análisis detallado para {symbol}: {str(e)}")

@router.get("/optimization-history/{symbol}", response_model=OptimizationHistoryResponse)
async def get_optimization_history(symbol: str):
    """Obtiene historial de optimizaciones para un símbolo"""
    try:
        history = await config_manager.get_optimization_history(symbol)
        
        if not history:
            return OptimizationHistoryResponse(
                symbol=symbol,
                optimizations=[]
            )
        
        return OptimizationHistoryResponse(**history)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo historial: {str(e)}")

@router.get("/optimization-history")
async def get_all_optimization_history():
    """Obtiene historial de optimizaciones para todos los símbolos"""
    try:
        history = await config_manager.get_optimization_history()
        return history
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo historial completo: {str(e)}")

@router.get("/strategies")
async def get_available_strategies():
    """Obtiene estrategias de optimización disponibles"""
    try:
        strategies = [
            {
                "id": strategy.value,
                "name": strategy.name.replace("_", " ").title(),
                "description": get_strategy_description(strategy)
            }
            for strategy in OptimizationStrategy
        ]
        
        return {
            "strategies": strategies,
            "total": len(strategies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estrategias: {str(e)}")

@router.post("/quick-optimize/{symbol}")
async def quick_optimize(symbol: str, investment_amount: float = 1000.0):
    """Optimización rápida con parámetros por defecto"""
    try:
        request = OptimizationRequest(
            symbol=symbol,
            strategy=OptimizationStrategy.GRID_OPTIMIZATION,
            investment_amount=investment_amount,
            risk_tolerance=0.5,
            max_grids=20,
            time_horizon=7
        )
        
        optimized_config = await config_manager.optimize_parameters(request)
        
        return {
            "status": "success",
            "message": f"Optimización rápida completada para {symbol}",
            "config": {
                "symbol": optimized_config.symbol,
                "min_price": optimized_config.min_price,
                "max_price": optimized_config.max_price,
                "grids": optimized_config.grids,
                "quantity": optimized_config.quantity,
                "confidence_score": optimized_config.confidence_score,
                "strategy": optimized_config.optimization_strategy
            },
            "backtest_results": optimized_config.backtest_results,
            "timestamp": optimized_config.timestamp.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en optimización rápida: {str(e)}")

@router.post("/compare-strategies/{symbol}")
async def compare_strategies(symbol: str, investment_amount: float = 1000.0):
    """Compara todas las estrategias de optimización para un símbolo"""
    try:
        results = {}
        
        for strategy in OptimizationStrategy:
            try:
                request = OptimizationRequest(
                    symbol=symbol,
                    strategy=strategy,
                    investment_amount=investment_amount,
                    risk_tolerance=0.5,
                    max_grids=20,
                    time_horizon=7
                )
                
                optimized_config = await config_manager.optimize_parameters(request)
                
                results[strategy.value] = {
                    "config": {
                        "min_price": optimized_config.min_price,
                        "max_price": optimized_config.max_price,
                        "grids": optimized_config.grids,
                        "quantity": optimized_config.quantity
                    },
                    "confidence_score": optimized_config.confidence_score,
                    "backtest_results": optimized_config.backtest_results
                }
                
            except Exception as e:
                results[strategy.value] = {
                    "error": str(e)
                }
        
        # Encontrar la mejor estrategia
        best_strategy = None
        best_score = 0
        
        for strategy_name, result in results.items():
            if "error" not in result and result["confidence_score"] > best_score:
                best_score = result["confidence_score"]
                best_strategy = strategy_name
        
        return {
            "symbol": symbol,
            "investment_amount": investment_amount,
            "strategies": results,
            "best_strategy": best_strategy,
            "best_score": best_score,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparando estrategias: {str(e)}")

@router.get("/health")
async def config_health_check():
    """Health check del sistema de optimización"""
    try:
        # Verificar que el ConfigManager esté funcionando
        market_data = await config_manager._get_market_data("BTC")
        
        return {
            "status": "healthy",
            "config_manager": "operational",
            "market_data_cache": len(config_manager.market_data_cache),
            "optimization_history": len(config_manager.optimization_history),
            "sample_market_data": {
                "symbol": market_data.symbol,
                "current_price": market_data.current_price,
                "volatility": market_data.volatility
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def get_strategy_description(strategy: OptimizationStrategy) -> str:
    """Obtiene descripción de una estrategia"""
    descriptions = {
        OptimizationStrategy.GRID_OPTIMIZATION: "Optimización tradicional de grid basada en rangos de precio",
        OptimizationStrategy.VOLATILITY_BASED: "Optimización basada en la volatilidad del mercado",
        OptimizationStrategy.VOLUME_BASED: "Optimización basada en el volumen de trading",
        OptimizationStrategy.MACHINE_LEARNING: "Optimización usando machine learning y datos históricos"
    }
    return descriptions.get(strategy, "Estrategia de optimización") 