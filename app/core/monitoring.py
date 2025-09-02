#!/usr/bin/env python3
"""
Sistema de Monitoreo en Tiempo Real para GridBot V2.5
Detecta problemas y envía alertas automáticas
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class Alert:
    """Estructura de alerta"""
    level: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: str
    category: str
    data: Dict

class MonitoringSystem:
    """
    Sistema de monitoreo en tiempo real
    """
    
    def __init__(self):
        self.alerts = []
        self.metrics = {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'current_balance': 0.0,
            'daily_pnl': 0.0,
            'hourly_pnl': 0.0,
            'last_update': datetime.now().isoformat()
        }
        self.thresholds = {
            'max_daily_loss': 0.05,      # 5% máximo pérdida diaria
            'max_hourly_loss': 0.03,     # 3% máximo pérdida por hora
            'max_consecutive_losses': 3,  # Máximo 3 pérdidas consecutivas
            'min_balance': 50.0,         # Balance mínimo en USDT
            'max_trade_loss': 0.02,      # 2% máximo pérdida por trade
        }
        self.load_data()
    
    def load_data(self):
        """Carga datos de monitoreo desde archivo"""
        try:
            if os.path.exists('monitoring_data.json'):
                with open('monitoring_data.json', 'r') as f:
                    data = json.load(f)
                    self.metrics.update(data.get('metrics', {}))
                    self.alerts = data.get('alerts', [])
                logger.info("✅ Datos de monitoreo cargados")
        except Exception as e:
            logger.error(f"Error cargando datos de monitoreo: {e}")
    
    def save_data(self):
        """Guarda datos de monitoreo en archivo"""
        try:
            data = {
                'metrics': self.metrics,
                'alerts': self.alerts,
                'last_save': datetime.now().isoformat()
            }
            with open('monitoring_data.json', 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando datos de monitoreo: {e}")
    
    def add_alert(self, level: str, message: str, category: str, data: Dict = None):
        """
        Agrega una alerta al sistema
        
        Args:
            level: Nivel de alerta (INFO, WARNING, ERROR, CRITICAL)
            message: Mensaje de la alerta
            category: Categoría de la alerta
            data: Datos adicionales
        """
        alert = Alert(
            level=level,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=category,
            data=data or {}
        )
        
        self.alerts.append(asdict(alert))
        
        # Mantener solo las últimas 100 alertas
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        # Log según nivel
        if level == 'CRITICAL':
            logger.critical(f"🚨 ALERTA CRÍTICA: {message}")
        elif level == 'ERROR':
            logger.error(f"❌ ALERTA ERROR: {message}")
        elif level == 'WARNING':
            logger.warning(f"⚠️ ALERTA WARNING: {message}")
        else:
            logger.info(f"ℹ️ ALERTA INFO: {message}")
        
        # Guardar datos
        self.save_data()
        
        # Enviar alerta si es crítica
        if level in ['CRITICAL', 'ERROR']:
            self._send_alert(alert)
    
    def update_metrics(self, **kwargs):
        """
        Actualiza métricas del sistema
        
        Args:
            **kwargs: Métricas a actualizar
        """
        self.metrics.update(kwargs)
        self.metrics['last_update'] = datetime.now().isoformat()
        
        # Verificar umbrales
        self._check_thresholds()
        
        # Guardar datos
        self.save_data()
    
    def _check_thresholds(self):
        """Verifica si se han excedido los umbrales"""
        
        # Verificar pérdida diaria
        if abs(self.metrics['daily_pnl']) > self.thresholds['max_daily_loss']:
            self.add_alert(
                'CRITICAL',
                f"Pérdida diaria excedida: {self.metrics['daily_pnl']:.2%}",
                'FINANCIAL',
                {'daily_pnl': self.metrics['daily_pnl']}
            )
        
        # Verificar pérdida por hora
        if abs(self.metrics['hourly_pnl']) > self.thresholds['max_hourly_loss']:
            self.add_alert(
                'WARNING',
                f"Pérdida por hora excedida: {self.metrics['hourly_pnl']:.2%}",
                'FINANCIAL',
                {'hourly_pnl': self.metrics['hourly_pnl']}
            )
        
        # Verificar balance mínimo
        if self.metrics['current_balance'] < self.thresholds['min_balance']:
            self.add_alert(
                'ERROR',
                f"Balance bajo: ${self.metrics['current_balance']:.2f}",
                'FINANCIAL',
                {'current_balance': self.metrics['current_balance']}
            )
        
        # Verificar ratio de trades fallidos
        if self.metrics['total_trades'] > 0:
            failure_rate = self.metrics['failed_trades'] / self.metrics['total_trades']
            if failure_rate > 0.5:  # Más del 50% de trades fallidos
                self.add_alert(
                    'WARNING',
                    f"Alto ratio de trades fallidos: {failure_rate:.2%}",
                    'TRADING',
                    {'failure_rate': failure_rate}
                )
    
    def record_trade(self, symbol: str, side: str, quantity: float, price: float, success: bool, profit_loss: float = 0.0):
        """
        Registra un trade en el sistema de monitoreo
        
        Args:
            symbol: Símbolo del trading pair
            side: Lado del trade (BUY/SELL)
            quantity: Cantidad
            price: Precio
            success: Si el trade fue exitoso
            profit_loss: Ganancia/pérdida del trade
        """
        # Actualizar métricas
        self.metrics['total_trades'] += 1
        
        if success:
            self.metrics['successful_trades'] += 1
            if profit_loss > 0:
                self.metrics['total_profit'] += profit_loss
            else:
                self.metrics['total_loss'] += abs(profit_loss)
        else:
            self.metrics['failed_trades'] += 1
        
        # Verificar pérdida por trade
        if profit_loss < 0 and abs(profit_loss) > self.thresholds['max_trade_loss']:
            self.add_alert(
                'WARNING',
                f"Pérdida por trade excedida: ${abs(profit_loss):.2f}",
                'TRADING',
                {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'profit_loss': profit_loss
                }
            )
        
        # Guardar datos
        self.save_data()
    
    def update_balance(self, new_balance: float):
        """
        Actualiza el balance actual
        
        Args:
            new_balance: Nuevo balance en USDT
        """
        old_balance = self.metrics['current_balance']
        self.metrics['current_balance'] = new_balance
        
        # Calcular cambio
        if old_balance > 0:
            change = (new_balance - old_balance) / old_balance
            self.metrics['daily_pnl'] += change
            
            # Alertar si hay pérdida significativa
            if change < -0.02:  # Pérdida del 2% o más
                self.add_alert(
                    'WARNING',
                    f"Pérdida significativa detectada: {change:.2%}",
                    'FINANCIAL',
                    {
                        'old_balance': old_balance,
                        'new_balance': new_balance,
                        'change': change
                    }
                )
        
        self.save_data()
    
    def get_status(self) -> Dict:
        """
        Obtiene el estado actual del sistema de monitoreo
        
        Returns:
            Dict: Estado del sistema
        """
        return {
            'metrics': self.metrics,
            'thresholds': self.thresholds,
            'recent_alerts': self.alerts[-10:],  # Últimas 10 alertas
            'total_alerts': len(self.alerts),
            'system_status': self._get_system_status()
        }
    
    def _get_system_status(self) -> str:
        """
        Determina el estado general del sistema
        
        Returns:
            str: Estado del sistema (HEALTHY, WARNING, CRITICAL)
        """
        # Verificar alertas críticas recientes
        recent_critical = [a for a in self.alerts[-10:] if a['level'] == 'CRITICAL']
        if recent_critical:
            return 'CRITICAL'
        
        # Verificar alertas de error recientes
        recent_errors = [a for a in self.alerts[-10:] if a['level'] == 'ERROR']
        if len(recent_errors) >= 3:
            return 'WARNING'
        
        # Verificar métricas financieras
        if self.metrics['daily_pnl'] < -0.03:  # Pérdida diaria del 3% o más
            return 'WARNING'
        
        return 'HEALTHY'
    
    def _send_alert(self, alert: Alert):
        """
        Envía una alerta (implementar según necesidad)
        
        Args:
            alert: Alerta a enviar
        """
        # TODO: Implementar envío de alertas por email/SMS
        logger.critical(f"🚨 ALERTA ENVIADA: {alert.message}")
    
    def reset_daily_metrics(self):
        """Resetea las métricas diarias"""
        self.metrics['daily_pnl'] = 0.0
        self.metrics['hourly_pnl'] = 0.0
        self.save_data()
        logger.info("🔄 Métricas diarias reseteadas")
    
    def get_performance_summary(self) -> Dict:
        """
        Obtiene un resumen de rendimiento
        
        Returns:
            Dict: Resumen de rendimiento
        """
        total_trades = self.metrics['total_trades']
        if total_trades == 0:
            return {'message': 'No hay trades registrados'}
        
        success_rate = self.metrics['successful_trades'] / total_trades
        total_pnl = self.metrics['total_profit'] - self.metrics['total_loss']
        
        return {
            'total_trades': total_trades,
            'success_rate': success_rate,
            'total_profit': self.metrics['total_profit'],
            'total_loss': self.metrics['total_loss'],
            'net_pnl': total_pnl,
            'current_balance': self.metrics['current_balance'],
            'daily_pnl': self.metrics['daily_pnl'],
            'system_status': self._get_system_status()
        }

# Instancia global del sistema de monitoreo
monitoring_system = MonitoringSystem()

def record_trade_event(symbol: str, side: str, quantity: float, price: float, success: bool, profit_loss: float = 0.0):
    """
    Función de conveniencia para registrar un trade
    
    Args:
        symbol: Símbolo del trading pair
        side: Lado del trade (BUY/SELL)
        quantity: Cantidad
        price: Precio
        success: Si el trade fue exitoso
        profit_loss: Ganancia/pérdida del trade
    """
    monitoring_system.record_trade(symbol, side, quantity, price, success, profit_loss)

def update_balance_monitoring(new_balance: float):
    """
    Función de conveniencia para actualizar balance
    
    Args:
        new_balance: Nuevo balance en USDT
    """
    monitoring_system.update_balance(new_balance)

def get_monitoring_status() -> Dict:
    """
    Función de conveniencia para obtener estado del monitoreo
    
    Returns:
        Dict: Estado del sistema de monitoreo
    """
    return monitoring_system.get_status()
