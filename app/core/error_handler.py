#!/usr/bin/env python3
"""
Sistema de manejo de errores escalable para el Grid Trading Bot
"""

import logging
import traceback
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from functools import wraps
import json
import os

logger = logging.getLogger(__name__)

class ErrorHandler:
    """
    Sistema centralizado de manejo de errores
    """
    
    def __init__(self):
        self.error_counts = {}
        self.error_thresholds = {
            "api_error": 5,
            "database_error": 3,
            "binance_error": 10,
            "risk_manager_error": 3,
            "telegram_error": 5
        }
        self.error_log_file = "logs/errors.json"
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Asegura que el directorio de logs existe"""
        try:
            os.makedirs("logs", exist_ok=True)
        except Exception as e:
            logger.error(f"Error creando directorio de logs: {e}")
    
    def log_error(self, error_type: str, error: Exception, context: Dict[str, Any] = None):
        """
        Registra un error con contexto
        """
        try:
            error_info = {
                "timestamp": datetime.now().isoformat(),
                "error_type": error_type,
                "error_message": str(error),
                "error_class": error.__class__.__name__,
                "traceback": traceback.format_exc(),
                "context": context or {}
            }
            
            # Incrementar contador de errores
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
            
            # Log del error
            logger.error(f"[{error_type}] {error}")
            if context:
                logger.error(f"Context: {context}")
            
            # Guardar en archivo
            self._save_error_to_file(error_info)
            
            # Verificar si se debe activar alerta
            self._check_error_threshold(error_type)
            
        except Exception as e:
            logger.error(f"Error registrando error: {e}")
    
    def _save_error_to_file(self, error_info: Dict[str, Any]):
        """Guarda el error en archivo JSON"""
        try:
            errors = []
            
            # Leer errores existentes
            if os.path.exists(self.error_log_file):
                try:
                    with open(self.error_log_file, 'r') as f:
                        errors = json.load(f)
                except:
                    errors = []
            
            # Agregar nuevo error
            errors.append(error_info)
            
            # Mantener solo los últimos 100 errores
            if len(errors) > 100:
                errors = errors[-100:]
            
            # Guardar
            with open(self.error_log_file, 'w') as f:
                json.dump(errors, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error guardando error en archivo: {e}")
    
    def _check_error_threshold(self, error_type: str):
        """Verifica si se debe activar una alerta por exceso de errores"""
        try:
            threshold = self.error_thresholds.get(error_type, 10)
            count = self.error_counts.get(error_type, 0)
            
            if count >= threshold:
                self._trigger_error_alert(error_type, count, threshold)
                
        except Exception as e:
            logger.error(f"Error verificando umbral de errores: {e}")
    
    def _trigger_error_alert(self, error_type: str, count: int, threshold: int):
        """Activa una alerta por exceso de errores"""
        try:
            from app.services.telegram_alert import send_telegram_alert
            
            message = f"🚨 ALERTA DE ERRORES\n\n"
            message += f"Tipo: {error_type}\n"
            message += f"Errores: {count}/{threshold}\n"
            message += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"Se requiere intervención manual."
            
            send_telegram_alert(message)
            
        except Exception as e:
            logger.error(f"Error enviando alerta de errores: {e}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen de errores"""
        try:
            return {
                "error_counts": self.error_counts,
                "error_thresholds": self.error_thresholds,
                "total_errors": sum(self.error_counts.values()),
                "critical_errors": [
                    error_type for error_type, count in self.error_counts.items()
                    if count >= self.error_thresholds.get(error_type, 10)
                ]
            }
        except Exception as e:
            logger.error(f"Error obteniendo resumen de errores: {e}")
            return {}
    
    def reset_error_count(self, error_type: str = None):
        """Resetea contadores de errores"""
        try:
            if error_type:
                self.error_counts[error_type] = 0
            else:
                self.error_counts.clear()
        except Exception as e:
            logger.error(f"Error reseteando contadores: {e}")

# Instancia global
error_handler = ErrorHandler()

def handle_errors(error_type: str, context: Dict[str, Any] = None):
    """
    Decorador para manejar errores en funciones
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler.log_error(error_type, e, context)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler.log_error(error_type, e, context)
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def safe_execute(func: Callable, error_type: str, context: Dict[str, Any] = None, default_return=None):
    """
    Ejecuta una función de forma segura con manejo de errores
    """
    try:
        if asyncio.iscoroutinefunction(func):
            return asyncio.create_task(func())
        else:
            return func()
    except Exception as e:
        error_handler.log_error(error_type, e, context)
        return default_return

class ErrorRecovery:
    """
    Sistema de recuperación automática de errores
    """
    
    @staticmethod
    async def retry_operation(operation: Callable, max_retries: int = 3, delay: float = 1.0):
        """
        Reintenta una operación con backoff exponencial
        """
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await operation()
                else:
                    return operation()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                
                wait_time = delay * (2 ** attempt)
                logger.warning(f"Reintentando operación en {wait_time}s (intento {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
    
    @staticmethod
    def create_fallback_value(value_type: str, default_value: Any = None):
        """
        Crea un valor de fallback basado en el tipo
        """
        fallbacks = {
            "dict": {},
            "list": [],
            "float": 0.0,
            "int": 0,
            "str": "",
            "bool": False
        }
        
        return fallbacks.get(value_type, default_value)
    
    @staticmethod
    async def graceful_degradation(primary_operation: Callable, fallback_operation: Callable, 
                                 error_type: str, context: Dict[str, Any] = None):
        """
        Implementa degradación graceful: intenta operación principal, si falla usa fallback
        """
        try:
            if asyncio.iscoroutinefunction(primary_operation):
                return await primary_operation()
            else:
                return primary_operation()
        except Exception as e:
            error_handler.log_error(error_type, e, context)
            logger.warning(f"Usando operación de fallback para {error_type}")
            
            try:
                if asyncio.iscoroutinefunction(fallback_operation):
                    return await fallback_operation()
                else:
                    return fallback_operation()
            except Exception as fallback_error:
                error_handler.log_error(f"{error_type}_fallback", fallback_error, context)
                raise fallback_error

# Funciones de utilidad para manejo de errores específicos
def handle_api_errors(func: Callable):
    """Decorador específico para errores de API"""
    return handle_errors("api_error")(func)

def handle_database_errors(func: Callable):
    """Decorador específico para errores de base de datos"""
    return handle_errors("database_error")(func)

def handle_binance_errors(func: Callable):
    """Decorador específico para errores de Binance"""
    return handle_errors("binance_error")(func)

def handle_risk_manager_errors(func: Callable):
    """Decorador específico para errores del risk manager"""
    return handle_errors("risk_manager_error")(func)

def handle_telegram_errors(func: Callable):
    """Decorador específico para errores de Telegram"""
    return handle_errors("telegram_error")(func) 