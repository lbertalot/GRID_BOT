#!/usr/bin/env python3
"""
Strategy Factory - Gestión de Estrategias de Trading

Este servicio gestiona la creación, configuración y ejecución de todas las
estrategias de trading disponibles en el sistema.
"""

import logging
from typing import Dict, List, Optional, Any, Type
from datetime import datetime

from app.strategies.base import (
    TradingStrategy, StrategyConfig, StrategyType, TradingResult
)
from app.strategies.dca_strategy import DCAStrategy, DCAConfig
from app.strategies.scalping_strategy import ScalpingStrategy, ScalpingConfig
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)

class StrategyFactory:
    """
    Factory para crear y gestionar estrategias de trading
    """
    
    def __init__(self):
        self.active_strategies: Dict[str, TradingStrategy] = {}
        self.strategy_configs: Dict[str, StrategyConfig] = {}
        self.strategy_metrics: Dict[str, Dict] = {}
        
        # Mapeo de tipos de estrategia a clases
        self.strategy_classes = {
            StrategyType.DCA: DCAStrategy,
            StrategyType.SCALPING: ScalpingStrategy,
            # Agregar más estrategias aquí cuando se implementen
        }
        
        # Mapeo de tipos de estrategia a configuraciones
        self.config_classes = {
            StrategyType.DCA: DCAConfig,
            StrategyType.SCALPING: ScalpingConfig,
            # Agregar más configuraciones aquí cuando se implementen
        }
        
        logger.info("Strategy Factory inicializado")
    
    def create_strategy(self, strategy_type: StrategyType, config: StrategyConfig) -> Optional[TradingStrategy]:
        """
        Crea una nueva estrategia de trading
        
        Args:
            strategy_type: Tipo de estrategia a crear
            config: Configuración de la estrategia
            
        Returns:
            Instancia de la estrategia o None si hay error
        """
        try:
            if strategy_type not in self.strategy_classes:
                logger.error(f"Tipo de estrategia no soportado: {strategy_type}")
                return None
            
            strategy_class = self.strategy_classes[strategy_type]
            strategy = strategy_class(config)
            
            logger.info(f"Estrategia {strategy_type.value} creada para {config.symbol}")
            return strategy
            
        except Exception as e:
            logger.error(f"Error creando estrategia {strategy_type.value}: {e}")
            return None
    
    def create_config(self, strategy_type: StrategyType, **kwargs) -> Optional[StrategyConfig]:
        """
        Crea una configuración para una estrategia
        
        Args:
            strategy_type: Tipo de estrategia
            **kwargs: Parámetros de configuración
            
        Returns:
            Configuración de la estrategia o None si hay error
        """
        try:
            if strategy_type not in self.config_classes:
                logger.error(f"Tipo de estrategia no soportado: {strategy_type}")
                return None
            
            config_class = self.config_classes[strategy_type]
            config = config_class(**kwargs)
            
            logger.info(f"Configuración creada para {strategy_type.value}")
            return config
            
        except Exception as e:
            logger.error(f"Error creando configuración para {strategy_type.value}: {e}")
            return None
    
    async def start_strategy(self, strategy_id: str, strategy: TradingStrategy) -> bool:
        """
        Inicia una estrategia de trading
        
        Args:
            strategy_id: ID único de la estrategia
            strategy: Instancia de la estrategia
            
        Returns:
            True si se inició correctamente
        """
        try:
            # Validar configuración
            if not await strategy.validate_config():
                logger.error(f"Configuración inválida para estrategia {strategy_id}")
                return False
            
            # Iniciar estrategia
            if not await strategy.start():
                logger.error(f"No se pudo iniciar estrategia {strategy_id}")
                return False
            
            # Registrar estrategia activa
            self.active_strategies[strategy_id] = strategy
            self.strategy_configs[strategy_id] = strategy.config
            self.strategy_metrics[strategy_id] = {
                "start_time": datetime.now(),
                "executions": 0,
                "total_profit": 0.0,
                "last_execution": None
            }
            
            logger.info(f"Estrategia {strategy_id} iniciada correctamente")
            
            # Enviar notificación
            await self._send_strategy_notification(f"🚀 Estrategia {strategy.config.strategy_type.value} iniciada para {strategy.config.symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error iniciando estrategia {strategy_id}: {e}")
            return False
    
    async def stop_strategy(self, strategy_id: str) -> bool:
        """
        Detiene una estrategia de trading
        
        Args:
            strategy_id: ID de la estrategia a detener
            
        Returns:
            True si se detuvo correctamente
        """
        try:
            if strategy_id not in self.active_strategies:
                logger.warning(f"Estrategia {strategy_id} no está activa")
                return False
            
            strategy = self.active_strategies[strategy_id]
            
            # Detener estrategia
            if not await strategy.stop():
                logger.error(f"No se pudo detener estrategia {strategy_id}")
                return False
            
            # Remover de estrategias activas
            del self.active_strategies[strategy_id]
            
            # Guardar métricas finales
            final_metrics = strategy.get_metrics()
            self.strategy_metrics[strategy_id]["final_metrics"] = final_metrics.dict()
            self.strategy_metrics[strategy_id]["stop_time"] = datetime.now()
            
            logger.info(f"Estrategia {strategy_id} detenida correctamente")
            
            # Enviar notificación
            await self._send_strategy_notification(f"🛑 Estrategia {strategy.config.strategy_type.value} detenida para {strategy.config.symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deteniendo estrategia {strategy_id}: {e}")
            return False
    
    async def execute_strategy(self, strategy_id: str) -> Optional[TradingResult]:
        """
        Ejecuta una estrategia específica
        
        Args:
            strategy_id: ID de la estrategia a ejecutar
            
        Returns:
            Resultado de la ejecución o None si hay error
        """
        try:
            if strategy_id not in self.active_strategies:
                logger.warning(f"Estrategia {strategy_id} no está activa")
                return None
            
            strategy = self.active_strategies[strategy_id]
            
            # Ejecutar estrategia
            result = await strategy.execute()
            
            # Actualizar métricas
            if result.success:
                await strategy.update_metrics(result)
                self.strategy_metrics[strategy_id]["executions"] += 1
                self.strategy_metrics[strategy_id]["total_profit"] += result.total_profit
                self.strategy_metrics[strategy_id]["last_execution"] = datetime.now()
            
            logger.info(f"Estrategia {strategy_id} ejecutada - Órdenes: {len(result.orders)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando estrategia {strategy_id}: {e}")
            return None
    
    async def execute_all_strategies(self) -> Dict[str, TradingResult]:
        """
        Ejecuta todas las estrategias activas
        
        Returns:
            Dict con los resultados de todas las estrategias
        """
        results = {}
        
        for strategy_id in list(self.active_strategies.keys()):
            try:
                result = await self.execute_strategy(strategy_id)
                if result:
                    results[strategy_id] = result
            except Exception as e:
                logger.error(f"Error ejecutando estrategia {strategy_id}: {e}")
        
        logger.info(f"Ejecutadas {len(results)} estrategias")
        return results
    
    async def get_strategy_status(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado de una estrategia específica
        
        Args:
            strategy_id: ID de la estrategia
            
        Returns:
            Estado de la estrategia o None si no existe
        """
        try:
            if strategy_id not in self.active_strategies:
                return None
            
            strategy = self.active_strategies[strategy_id]
            status = await strategy.get_status()
            
            # Agregar métricas del factory
            if strategy_id in self.strategy_metrics:
                status["factory_metrics"] = self.strategy_metrics[strategy_id]
            
            return status
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de estrategia {strategy_id}: {e}")
            return None
    
    async def get_all_strategies_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene el estado de todas las estrategias activas
        
        Returns:
            Dict con el estado de todas las estrategias
        """
        statuses = {}
        
        for strategy_id in self.active_strategies:
            status = await self.get_strategy_status(strategy_id)
            if status:
                statuses[strategy_id] = status
        
        return statuses
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de estrategias disponibles
        
        Returns:
            Lista de estrategias disponibles con sus configuraciones
        """
        strategies = []
        
        for strategy_type, config_class in self.config_classes.items():
            strategies.append({
                "type": strategy_type.value,
                "name": strategy_type.name,
                "description": self._get_strategy_description(strategy_type),
                "config_fields": self._get_config_fields(config_class)
            })
        
        return strategies
    
    def _get_strategy_description(self, strategy_type: StrategyType) -> str:
        """Obtiene la descripción de una estrategia"""
        descriptions = {
            StrategyType.DCA: "Dollar Cost Averaging - Compra una cantidad fija en intervalos regulares",
            StrategyType.SCALPING: "Scalping - Busca pequeñas ganancias en movimientos rápidos",
            StrategyType.GRID: "Grid Trading - Órdenes en niveles de precio específicos",
            StrategyType.ARBITRAGE: "Arbitraje - Explota diferencias de precio entre exchanges",
            StrategyType.RSI_MACD: "RSI + MACD - Estrategia basada en indicadores técnicos",
            StrategyType.TRAILING_STOP: "Trailing Stop - Stop loss dinámico que sigue el precio"
        }
        
        return descriptions.get(strategy_type, "Descripción no disponible")
    
    def _get_config_fields(self, config_class: Type[StrategyConfig]) -> List[Dict[str, Any]]:
        """Obtiene los campos de configuración de una estrategia"""
        try:
            # Crear una instancia temporal para obtener los campos
            temp_config = config_class(symbol="TEMP", strategy_type=StrategyType.DCA, investment_amount=100.0)
            fields = []
            
            for field_name, field_info in temp_config.__fields__.items():
                if field_name not in ["symbol", "strategy_type"]:  # Campos base
                    fields.append({
                        "name": field_name,
                        "type": str(field_info.annotation),
                        "default": field_info.default,
                        "description": field_info.description if hasattr(field_info, 'description') else ""
                    })
            
            return fields
            
        except Exception as e:
            logger.error(f"Error obteniendo campos de configuración: {e}")
            return []
    
    async def _send_strategy_notification(self, message: str):
        """Envía notificación sobre cambios en estrategias"""
        try:
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error enviando notificación de estrategia: {e}")
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen de todas las estrategias
        
        Returns:
            Resumen de estrategias activas y métricas
        """
        active_count = len(self.active_strategies)
        total_profit = sum(
            metrics.get("total_profit", 0) 
            for metrics in self.strategy_metrics.values()
        )
        total_executions = sum(
            metrics.get("executions", 0) 
            for metrics in self.strategy_metrics.values()
        )
        
        return {
            "active_strategies": active_count,
            "total_profit": total_profit,
            "total_executions": total_executions,
            "strategy_types": list(set(
                strategy.config.strategy_type.value 
                for strategy in self.active_strategies.values()
            ))
        }

# Instancia global del factory
strategy_factory = StrategyFactory() 