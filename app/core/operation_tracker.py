"""
Operation Tracker - Tracking Completo de Operaciones y Pérdidas
GridBot v2.5 - Componente de Integridad Integrado
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
from enum import Enum

from app.services.binance_client_singleton import binance_client_singleton
from app.core.database import Database
from app.core.telegram_bot import TelegramBot
from app.core.grafana_metrics import GrafanaMetrics
from app.core.circuit_breakers import CircuitBreakers
from app.core.config import settings

logger = logging.getLogger(__name__)

class OperationStatus(Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class OperationType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    GRID_BUY = "GRID_BUY"
    GRID_SELL = "GRID_SELL"
    EMERGENCY_BUY = "EMERGENCY_BUY"
    EMERGENCY_SELL = "EMERGENCY_SELL"

class OperationTracker:
    def __init__(self):
        self.config = settings
        self.binance_client = binance_client_singleton
        self.db = Database()
        self.telegram_bot = TelegramBot()
        self.grafana_metrics = GrafanaMetrics()
        self.circuit_breakers = CircuitBreakers()
        
        # Configuración de tracking
        self.track_slippage = True
        self.track_fees = True
        self.track_partial_fills = True
        self.track_failed_operations = True
        
        # Umbrales de alerta
        self.slippage_alert_threshold = Decimal('0.002')  # 0.2%
        self.fee_alert_threshold = Decimal('0.005')       # 0.5%
        self.failure_rate_alert_threshold = Decimal('0.05')  # 5%
        
        # Estado del tracker
        self.active_operations = {}
        self.operation_history = []
        self.failed_operations = []
        self.partial_fills = []
        
        # Métricas de operaciones
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations_count = 0
        self.partial_fills_count = 0
        self.total_slippage = Decimal('0')
        self.total_fees = Decimal('0')
        
    async def track_operation(self, operation_data: Dict[str, Any]) -> str:
        """Registrar operación antes de ejecutar"""
        try:
            # Generar ID único de operación
            operation_id = self.generate_operation_id()
            
            # Preparar datos de operación
            operation_record = {
                'operation_id': operation_id,
                'timestamp': datetime.now().isoformat(),
                'asset': operation_data['asset'],
                'operation_type': operation_data['type'],
                'side': operation_data['side'],
                'quantity': Decimal(str(operation_data['quantity'])),
                'intended_price': Decimal(str(operation_data['price'])),
                'status': OperationStatus.PENDING.value,
                'intended_value': Decimal(str(operation_data['quantity'])) * Decimal(str(operation_data['price'])),
                'user_id': operation_data.get('user_id'),
                'strategy_id': operation_data.get('strategy_id'),
                'grid_level': operation_data.get('grid_level'),
                'metadata': operation_data.get('metadata', {})
            }
            
            # Registrar en base de datos
            await self.db.insert_operation_record(operation_record)
            
            # Agregar a operaciones activas
            self.active_operations[operation_id] = operation_record
            
            # Actualizar métricas
            self.total_operations += 1
            
            logger.info(f"📝 Operación registrada: {operation_id} - {operation_data['asset']} {operation_data['side']}")
            
            return operation_id
            
        except Exception as e:
            logger.error(f"❌ Error registrando operación: {e}")
            raise
    
    async def update_operation_status(self, operation_id: str, status: OperationStatus, result_data: Dict = None):
        """Actualizar estado de operación"""
        try:
            if operation_id not in self.active_operations:
                logger.warning(f"⚠️ Operación {operation_id} no encontrada en operaciones activas")
                return
            
            operation = self.active_operations[operation_id]
            old_status = operation['status']
            
            # Actualizar estado
            operation['status'] = status.value
            operation['status_updated_at'] = datetime.now().isoformat()
            
            # Procesar resultado si está disponible
            if result_data and status == OperationStatus.COMPLETED:
                await self.process_completed_operation(operation_id, result_data)
            elif status == OperationStatus.FAILED:
                await self.process_failed_operation(operation_id, result_data)
            elif status == OperationStatus.PARTIALLY_FILLED:
                await self.process_partial_fill(operation_id, result_data)
            
            # Actualizar en base de datos
            await self.db.update_operation_status(operation_id, status.value, result_data)
            
            # Enviar alertas si es necesario
            await self.check_and_send_alerts(operation_id, old_status, status)
            
            # Actualizar métricas de Grafana
            await self.update_grafana_metrics()
            
            logger.info(f"📊 Operación {operation_id} actualizada: {old_status} -> {status.value}")
            
        except Exception as e:
            logger.error(f"❌ Error actualizando estado de operación {operation_id}: {e}")
    
    async def process_completed_operation(self, operation_id: str, result_data: Dict):
        """Procesar operación completada exitosamente"""
        try:
            operation = self.active_operations[operation_id]
            
            # Extraer datos del resultado
            executed_price = Decimal(str(result_data.get('executed_price', 0)))
            executed_quantity = Decimal(str(result_data.get('executed_quantity', 0)))
            executed_value = executed_price * executed_quantity
            fees = Decimal(str(result_data.get('fees', 0)))
            
            # Calcular slippage
            intended_price = operation['intended_price']
            slippage = abs(executed_price - intended_price) / intended_price if intended_price > 0 else 0
            
            # Actualizar operación con datos reales
            operation.update({
                'executed_price': executed_price,
                'executed_quantity': executed_quantity,
                'executed_value': executed_value,
                'fees': fees,
                'slippage': slippage,
                'completion_timestamp': datetime.now().isoformat()
            })
            
            # Actualizar métricas
            self.successful_operations += 1
            self.total_slippage += slippage
            self.total_fees += fees
            
            # Verificar si hay alertas por slippage o fees
            await self.check_slippage_and_fee_alerts(operation_id, slippage, fees)
            
            # Mover a historial
            self.operation_history.append(operation)
            del self.active_operations[operation_id]
            
            logger.info(f"✅ Operación {operation_id} completada exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error procesando operación completada {operation_id}: {e}")
    
    async def process_failed_operation(self, operation_id: str, result_data: Dict):
        """Procesar operación fallida"""
        try:
            operation = self.active_operations[operation_id]
            
            # Extraer información del fallo
            failure_reason = result_data.get('failure_reason', 'Unknown error')
            failure_code = result_data.get('failure_code')
            failure_timestamp = datetime.now().isoformat()
            
            # Actualizar operación con datos del fallo
            operation.update({
                'failure_reason': failure_reason,
                'failure_code': failure_code,
                'failure_timestamp': failure_timestamp
            })
            
            # Actualizar métricas
            self.failed_operations_count += 1
            
            # Agregar a lista de operaciones fallidas
            self.failed_operations.append(operation)
            
            # Mover a historial
            self.operation_history.append(operation)
            del self.active_operations[operation_id]
            
            logger.warning(f"❌ Operación {operation_id} falló: {failure_reason}")
            
        except Exception as e:
            logger.error(f"❌ Error procesando operación fallida {operation_id}: {e}")
    
    async def process_partial_fill(self, operation_id: str, result_data: Dict):
        """Procesar operación parcialmente ejecutada"""
        try:
            operation = self.active_operations[operation_id]
            
            # Extraer datos del partial fill
            executed_price = Decimal(str(result_data.get('executed_price', 0)))
            executed_quantity = Decimal(str(result_data.get('executed_quantity', 0)))
            remaining_quantity = Decimal(str(result_data.get('remaining_quantity', 0)))
            fees = Decimal(str(result_data.get('fees', 0)))
            
            # Calcular slippage
            intended_price = operation['intended_price']
            slippage = abs(executed_price - intended_price) / intended_price if intended_price > 0 else 0
            
            # Actualizar operación
            operation.update({
                'executed_price': executed_price,
                'executed_quantity': executed_quantity,
                'remaining_quantity': remaining_quantity,
                'fees': fees,
                'slippage': slippage,
                'partial_fill_timestamp': datetime.now().isoformat()
            })
            
            # Actualizar métricas
            self.partial_fills_count += 1
            self.total_slippage += slippage
            self.total_fees += fees
            
            # Crear nueva operación para la cantidad restante
            if remaining_quantity > 0:
                remaining_operation_data = {
                    'asset': operation['asset'],
                    'type': operation['operation_type'],
                    'side': operation['side'],
                    'quantity': remaining_quantity,
                    'price': intended_price,
                    'user_id': operation.get('user_id'),
                    'strategy_id': operation.get('strategy_id'),
                    'grid_level': operation.get('grid_level'),
                    'metadata': {**operation.get('metadata', {}), 'partial_fill_remainder': True}
                }
                
                new_operation_id = await self.track_operation(remaining_operation_data)
                logger.info(f"🔄 Nueva operación creada para cantidad restante: {new_operation_id}")
            
            logger.info(f"⚠️ Operación {operation_id} parcialmente ejecutada")
            
        except Exception as e:
            logger.error(f"❌ Error procesando partial fill {operation_id}: {e}")
    
    async def check_slippage_and_fee_alerts(self, operation_id: str, slippage: Decimal, fees: Decimal):
        """Verificar y enviar alertas por slippage y fees"""
        try:
            alerts = []
            
            # Verificar slippage
            if slippage > self.slippage_alert_threshold:
                alerts.append(f"⚠️ Slippage alto: {slippage:.3%} (umbral: {self.slippage_alert_threshold:.3%})")
            
            # Verificar fees
            if fees > self.fee_alert_threshold:
                alerts.append(f"⚠️ Fees altos: ${fees:.4f} (umbral: ${self.fee_alert_threshold:.4f})")
            
            # Enviar alertas si es necesario
            if alerts:
                operation = self.active_operations.get(operation_id, {})
                alert_message = f"🚨 ALERTA OPERACIÓN {operation_id}\n"
                alert_message += f"Asset: {operation.get('asset', 'N/A')}\n"
                alert_message += f"Tipo: {operation.get('operation_type', 'N/A')}\n"
                alert_message += "\n".join(alerts)
                
                await self.telegram_bot.send_alert(alert_message)
                
        except Exception as e:
            logger.error(f"❌ Error verificando alertas de slippage/fees: {e}")
    
    async def check_and_send_alerts(self, operation_id: str, old_status: str, new_status: OperationStatus):
        """Verificar y enviar alertas por cambios de estado"""
        try:
            # Alertas por fallos
            if new_status == OperationStatus.FAILED:
                operation = self.active_operations.get(operation_id, {})
                alert_message = f"❌ OPERACIÓN FALLIDA: {operation_id}\n"
                alert_message += f"Asset: {operation.get('asset', 'N/A')}\n"
                alert_message += f"Tipo: {operation.get('operation_type', 'N/A')}\n"
                alert_message += f"Razón: {operation.get('failure_reason', 'N/A')}"
                
                await self.telegram_bot.send_alert(alert_message)
            
            # Alertas por partial fills
            elif new_status == OperationStatus.PARTIALLY_FILLED:
                operation = self.active_operations.get(operation_id, {})
                alert_message = f"⚠️ OPERACIÓN PARCIALMENTE EJECUTADA: {operation_id}\n"
                alert_message += f"Asset: {operation.get('asset', 'N/A')}\n"
                alert_message += f"Ejecutado: {operation.get('executed_quantity', 0)}\n"
                alert_message += f"Restante: {operation.get('remaining_quantity', 0)}"
                
                await self.telegram_bot.send_alert(alert_message)
                
        except Exception as e:
            logger.error(f"❌ Error verificando alertas de estado: {e}")
    
    async def update_grafana_metrics(self):
        """Actualizar métricas en Grafana"""
        try:
            # Métricas de operaciones
            await self.grafana_metrics.record_metric('total_operations', self.total_operations)
            await self.grafana_metrics.record_metric('successful_operations', self.successful_operations)
            await self.grafana_metrics.record_metric('failed_operations', self.failed_operations_count)
            await self.grafana_metrics.record_metric('partial_fills', self.partial_fills_count)
            
            # Calcular tasas
            success_rate = self.successful_operations / self.total_operations if self.total_operations > 0 else 0
            failure_rate = self.failed_operations_count / self.total_operations if self.total_operations > 0 else 0
            
            await self.grafana_metrics.record_metric('operation_success_rate', success_rate)
            await self.grafana_metrics.record_metric('operation_failure_rate', failure_rate)
            
            # Métricas de slippage y fees
            avg_slippage = self.total_slippage / self.successful_operations if self.successful_operations > 0 else 0
            avg_fees = self.total_fees / self.successful_operations if self.successful_operations > 0 else 0
            
            await self.grafana_metrics.record_metric('average_slippage', float(avg_slippage))
            await self.grafana_metrics.record_metric('average_fees', float(avg_fees))
            await self.grafana_metrics.record_metric('total_slippage', float(self.total_slippage))
            await self.grafana_metrics.record_metric('total_fees', float(self.total_fees))
            
            # Métricas de operaciones activas
            active_operations_count = len(self.active_operations)
            await self.grafana_metrics.record_metric('active_operations', active_operations_count)
            
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas de Grafana: {e}")
    
    async def get_operation_summary(self) -> Dict:
        """Obtener resumen de operaciones"""
        return {
            'total_operations': self.total_operations,
            'successful_operations': self.successful_operations,
            'failed_operations': self.failed_operations_count,
            'partial_fills': self.partial_fills_count,
            'active_operations': len(self.active_operations),
            'success_rate': self.successful_operations / self.total_operations if self.total_operations > 0 else 0,
            'failure_rate': self.failed_operations_count / self.total_operations if self.total_operations > 0 else 0,
            'average_slippage': float(self.total_slippage / self.successful_operations if self.successful_operations > 0 else 0),
            'average_fees': float(self.total_fees / self.successful_operations if self.successful_operations > 0 else 0),
            'total_slippage': float(self.total_slippage),
            'total_fees': float(self.total_fees)
        }
    
    async def get_failed_operations_summary(self) -> List[Dict]:
        """Obtener resumen de operaciones fallidas"""
        return self.failed_operations[-50:]  # Últimas 50 operaciones fallidas
    
    async def get_partial_fills_summary(self) -> List[Dict]:
        """Obtener resumen de partial fills"""
        return self.partial_fills[-50:]  # Últimas 50 operaciones parciales
    
    async def force_operation_check(self):
        """Forzar verificación de estado de operaciones activas"""
        logger.info("🔄 Forzando verificación de operaciones activas")
        
        for operation_id, operation in list(self.active_operations.items()):
            try:
                # Verificar estado en Binance (simulado por ahora)
                order_status = {
                    'status': 'FILLED',
                    'executed_price': 50001,
                    'executed_quantity': 0.001,
                    'fees': 0.0001
                }
                
                # Actualizar estado según respuesta de Binance
                if order_status['status'] == 'FILLED':
                    await self.update_operation_status(operation_id, OperationStatus.COMPLETED, order_status)
                elif order_status['status'] == 'PARTIALLY_FILLED':
                    await self.update_operation_status(operation_id, OperationStatus.PARTIALLY_FILLED, order_status)
                elif order_status['status'] == 'CANCELED':
                    await self.update_operation_status(operation_id, OperationStatus.CANCELLED, order_status)
                elif order_status['status'] == 'EXPIRED':
                    await self.update_operation_status(operation_id, OperationStatus.EXPIRED, order_status)
                
            except Exception as e:
                logger.error(f"❌ Error verificando operación {operation_id}: {e}")
    
    def generate_operation_id(self) -> str:
        """Generar ID único de operación"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        random_suffix = str(hash(timestamp))[-6:]
        return f"OP_{timestamp}_{random_suffix}"
    
    async def cleanup_old_operations(self, days_old: int = 30):
        """Limpiar operaciones antiguas de la memoria"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # Limpiar historial
            self.operation_history = [
                op for op in self.operation_history 
                if datetime.fromisoformat(op.get('timestamp', '2000-01-01')) > cutoff_date
            ]
            
            # Limpiar operaciones fallidas
            self.failed_operations = [
                op for op in self.failed_operations 
                if datetime.fromisoformat(op.get('timestamp', '2000-01-01')) > cutoff_date
            ]
            
            # Limpiar partial fills
            self.partial_fills = [
                op for op in self.partial_fills 
                if datetime.fromisoformat(op.get('timestamp', '2000-01-01')) > cutoff_date
            ]
            
            logger.info(f"🧹 Limpieza completada. Operaciones antiguas removidas (>{days_old} días)")
            
        except Exception as e:
            logger.error(f"❌ Error en limpieza de operaciones: {e}")
    
    async def start_periodic_cleanup(self, cleanup_interval: int = 86400):  # 24 horas
        """Iniciar limpieza periódica de operaciones"""
        logger.info("🚀 Iniciando limpieza periódica de operaciones")
        
        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                await self.cleanup_old_operations()
                
            except Exception as e:
                logger.error(f"❌ Error en limpieza periódica: {e}")
                await asyncio.sleep(3600)  # Esperar 1 hora antes de reintentar
