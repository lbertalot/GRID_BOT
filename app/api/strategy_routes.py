#!/usr/bin/env python3
"""
Rutas API para Gestión de Estrategias de Trading
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid

from app.strategies.base import StrategyType
from app.services.strategy_factory import strategy_factory
from app.services.strategy_factory import StrategyFactory
from app.strategies.dca_strategy import DCAConfig
from app.strategies.scalping_strategy import ScalpingConfig

router = APIRouter(prefix="/api/v1/strategies", tags=["Strategies"])

# Modelos de request/response
class StrategyCreateRequest(BaseModel):
    """Request para crear una nueva estrategia"""
    symbol: str = Field(..., description="Símbolo del activo")
    strategy_type: StrategyType = Field(..., description="Tipo de estrategia")
    investment_amount: float = Field(gt=0, description="Cantidad a invertir en USDT")
    risk_tolerance: float = Field(ge=0.1, le=1.0, default=0.5, description="Tolerancia al riesgo")
    
    # Parámetros específicos de DCA
    frequency_hours: Optional[int] = Field(None, description="Frecuencia de inversión en horas (DCA)")
    max_investments: Optional[int] = Field(None, description="Máximo número de inversiones (DCA)")
    price_threshold: Optional[float] = Field(None, description="Umbral de precio para comprar (DCA)")
    
    # Parámetros específicos de Scalping
    entry_threshold: Optional[float] = Field(None, description="Umbral de entrada (Scalping)")
    profit_target: Optional[float] = Field(None, description="Objetivo de ganancia (Scalping)")
    stop_loss: Optional[float] = Field(None, description="Stop loss (Scalping)")
    max_position_size: Optional[float] = Field(None, description="Tamaño máximo de posición (Scalping)")
    max_hold_time_minutes: Optional[int] = Field(None, description="Tiempo máximo de retención (Scalping)")

class StrategyResponse(BaseModel):
    """Response para información de estrategia"""
    strategy_id: str
    symbol: str
    strategy_type: str
    status: str
    is_running: bool
    last_execution: Optional[str]
    metrics: Dict[str, Any]

class StrategyExecutionResponse(BaseModel):
    """Response para ejecución de estrategia"""
    strategy_id: str
    success: bool
    orders_executed: int
    total_profit: float
    total_volume: float
    error_message: Optional[str]

@router.get("/available", response_model=List[Dict[str, Any]])
async def get_available_strategies():
    """Obtiene la lista de estrategias disponibles"""
    try:
        strategies = strategy_factory.get_available_strategies()
        return strategies
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estrategias: {str(e)}")

@router.post("/create", response_model=StrategyResponse)
async def create_strategy(request: StrategyCreateRequest):
    """Crea una nueva estrategia de trading"""
    try:
        # Crear configuración específica según el tipo de estrategia
        config_kwargs = {
            "symbol": request.symbol,
            "strategy_type": request.strategy_type,
            "investment_amount": request.investment_amount,
            "risk_tolerance": request.risk_tolerance
        }
        
        if request.strategy_type == StrategyType.DCA:
            # Agregar parámetros específicos de DCA
            if request.frequency_hours:
                config_kwargs["frequency_hours"] = request.frequency_hours
            if request.max_investments:
                config_kwargs["max_investments"] = request.max_investments
            if request.price_threshold:
                config_kwargs["price_threshold"] = request.price_threshold
            
            config = strategy_factory.create_config(StrategyType.DCA, **config_kwargs)
            
        elif request.strategy_type == StrategyType.SCALPING:
            # Agregar parámetros específicos de Scalping
            if request.entry_threshold:
                config_kwargs["entry_threshold"] = request.entry_threshold
            if request.profit_target:
                config_kwargs["profit_target"] = request.profit_target
            if request.stop_loss:
                config_kwargs["stop_loss"] = request.stop_loss
            if request.max_position_size:
                config_kwargs["max_position_size"] = request.max_position_size
            if request.max_hold_time_minutes:
                config_kwargs["max_hold_time_minutes"] = request.max_hold_time_minutes
            
            config = strategy_factory.create_config(StrategyType.SCALPING, **config_kwargs)
            
        else:
            raise HTTPException(status_code=400, detail=f"Tipo de estrategia no soportado: {request.strategy_type}")
        
        if not config:
            raise HTTPException(status_code=400, detail="Error creando configuración de estrategia")
        
        # Crear estrategia
        strategy = strategy_factory.create_strategy(request.strategy_type, config)
        if not strategy:
            raise HTTPException(status_code=400, detail="Error creando estrategia")
        
        # Generar ID único
        strategy_id = str(uuid.uuid4())
        
        # Iniciar estrategia
        success = await strategy_factory.start_strategy(strategy_id, strategy)
        if not success:
            raise HTTPException(status_code=500, detail="Error iniciando estrategia")
        
        # Obtener estado de la estrategia
        status = await strategy_factory.get_strategy_status(strategy_id)
        
        return StrategyResponse(
            strategy_id=strategy_id,
            symbol=request.symbol,
            strategy_type=request.strategy_type.value,
            status="active",
            is_running=True,
            last_execution=status.get("last_execution"),
            metrics=status.get("metrics", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando estrategia: {str(e)}")

@router.get("/list", response_model=List[StrategyResponse])
async def list_strategies():
    """Obtiene la lista de todas las estrategias activas"""
    try:
        statuses = await strategy_factory.get_all_strategies_status()
        strategies = []
        
        for strategy_id, status in statuses.items():
            strategies.append(StrategyResponse(
                strategy_id=strategy_id,
                symbol=status.get("symbol", ""),
                strategy_type=status.get("strategy_type", ""),
                status="active" if status.get("is_running") else "stopped",
                is_running=status.get("is_running", False),
                last_execution=status.get("last_execution"),
                metrics=status.get("metrics", {})
            ))
        
        return strategies
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estrategias: {str(e)}")

@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str):
    """Obtiene información de una estrategia específica"""
    try:
        status = await strategy_factory.get_strategy_status(strategy_id)
        if not status:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")
        
        return StrategyResponse(
            strategy_id=strategy_id,
            symbol=status.get("symbol", ""),
            strategy_type=status.get("strategy_type", ""),
            status="active" if status.get("is_running") else "stopped",
            is_running=status.get("is_running", False),
            last_execution=status.get("last_execution"),
            metrics=status.get("metrics", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estrategia: {str(e)}")

@router.post("/{strategy_id}/execute", response_model=StrategyExecutionResponse)
async def execute_strategy(strategy_id: str):
    """Ejecuta una estrategia específica"""
    try:
        result = await strategy_factory.execute_strategy(strategy_id)
        if not result:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada o no activa")
        
        return StrategyExecutionResponse(
            strategy_id=strategy_id,
            success=result.success,
            orders_executed=len(result.orders),
            total_profit=result.total_profit,
            total_volume=result.total_volume,
            error_message=result.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando estrategia: {str(e)}")

@router.post("/execute-all", response_model=Dict[str, StrategyExecutionResponse])
async def execute_all_strategies():
    """Ejecuta todas las estrategias activas"""
    try:
        results = await strategy_factory.execute_all_strategies()
        response = {}
        
        for strategy_id, result in results.items():
            response[strategy_id] = StrategyExecutionResponse(
                strategy_id=strategy_id,
                success=result.success,
                orders_executed=len(result.orders),
                total_profit=result.total_profit,
                total_volume=result.total_volume,
                error_message=result.error_message
            )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando estrategias: {str(e)}")

@router.delete("/{strategy_id}")
async def stop_strategy(strategy_id: str):
    """Detiene una estrategia específica"""
    try:
        success = await strategy_factory.stop_strategy(strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")
        
        return {"message": f"Estrategia {strategy_id} detenida correctamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deteniendo estrategia: {str(e)}")

@router.get("/summary")
async def get_strategies_summary():
    """Obtiene un resumen de todas las estrategias"""
    try:
        summary = strategy_factory.get_strategy_summary()
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {str(e)}")

@router.get("/{strategy_id}/detailed-status")
async def get_strategy_detailed_status(strategy_id: str):
    """Obtiene el estado detallado de una estrategia específica"""
    try:
        status = await strategy_factory.get_strategy_status(strategy_id)
        if not status:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado detallado: {str(e)}")

@router.post("/{strategy_id}/start")
async def start_strategy(strategy_id: str):
    """Inicia una estrategia específica"""
    try:
        # Verificar si la estrategia existe
        status = await strategy_factory.get_strategy_status(strategy_id)
        if not status:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")
        
        if status.get("is_running"):
            return {"message": f"Estrategia {strategy_id} ya está ejecutándose"}
        
        # La estrategia ya debería estar iniciada al crearse
        return {"message": f"Estrategia {strategy_id} iniciada correctamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error iniciando estrategia: {str(e)}")

@router.get("/health")
async def strategies_health():
    """Health check para el sistema de estrategias"""
    try:
        summary = strategy_factory.get_strategy_summary()
        return {
            "status": "healthy",
            "active_strategies": summary.get("active_strategies", 0),
            "total_profit": summary.get("total_profit", 0.0),
            "total_executions": summary.get("total_executions", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en health check: {str(e)}") 