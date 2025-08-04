"""
Sistema centralizado de métricas optimizado para Grafana
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from prometheus_client import Gauge, Counter, Histogram, Summary, CollectorRegistry
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.trade import Trade
from app.services.binance_client_singleton import binance_client_singleton

logger = logging.getLogger(__name__)

class MetricsManager:
    """
    Gestor centralizado de métricas para el sistema de trading
    """
    
    def __init__(self):
        # Crear un registro separado para evitar conflictos
        self.registry = CollectorRegistry()
        
        # Métricas de trading
        self.trading_active = Gauge('trading_active', 'Estado del sistema de trading (1=activo, 0=inactivo)', registry=self.registry)
        self.trades_total = Counter('trades_total', 'Total de trades ejecutados', ['symbol', 'side'], registry=self.registry)
        self.trades_daily = Counter('trades_daily', 'Trades ejecutados hoy', ['symbol', 'side'], registry=self.registry)
        
        # Métricas de rentabilidad
        self.profit_total_usdt = Gauge('profit_total_usdt', 'Ganancia total acumulada en USDT', ['strategy'], registry=self.registry)
        self.profit_daily_usdt = Gauge('profit_daily_usdt', 'Ganancia diaria en USDT', ['strategy'], registry=self.registry)
        self.profit_monthly_usdt = Gauge('profit_monthly_usdt', 'Ganancia mensual en USDT', ['strategy'], registry=self.registry)
        self.roi_total_percent = Gauge('roi_total_percent', 'ROI total en porcentaje', ['strategy'], registry=self.registry)
        self.roi_daily_percent = Gauge('roi_daily_percent', 'ROI diario en porcentaje', ['strategy'], registry=self.registry)
        
        # Métricas de portafolio
        self.portfolio_total_value_usdt = Gauge('portfolio_total_value_usdt', 'Valor total del portafolio en USDT', registry=self.registry)
        self.portfolio_asset_value_usdt = Gauge('portfolio_asset_value_usdt', 'Valor de cada activo en USDT', ['asset'], registry=self.registry)
        self.portfolio_asset_balance = Gauge('portfolio_asset_balance', 'Balance de cada activo', ['asset'], registry=self.registry)
        
        # Métricas de rendimiento
        self.trade_execution_time = Histogram('trade_execution_time_seconds', 'Tiempo de ejecución de trades', ['symbol'], registry=self.registry)
        self.trade_success_rate = Gauge('trade_success_rate', 'Tasa de éxito de trades', ['symbol'], registry=self.registry)
        self.trade_volume_usdt = Counter('trade_volume_usdt', 'Volumen total de trading en USDT', ['symbol', 'side'], registry=self.registry)
        
        # Métricas de señales
        self.signals_detected = Counter('signals_detected', 'Señales detectadas', ['symbol', 'action'], registry=self.registry)
        self.signals_executed = Counter('signals_executed', 'Señales ejecutadas', ['symbol', 'action'], registry=self.registry)
        
        # Métricas de errores
        self.errors_total = Counter('errors_total', 'Total de errores', ['type'], registry=self.registry)
        self.api_errors = Counter('api_errors', 'Errores de API', ['service'], registry=self.registry)
        
        # Estado del sistema
        self.system_health = Gauge('system_health', 'Estado de salud del sistema (1=sano, 0=enfermo)', registry=self.registry)
        self.last_update_timestamp = Gauge('last_update_timestamp', 'Timestamp de la última actualización de métricas', registry=self.registry)
        
        # Inicializar métricas
        self._initialize_metrics()
    
    def _initialize_metrics(self):
        """Inicializa las métricas con valores por defecto"""
        try:
            self.trading_active.set(1.0)  # Sistema activo
            self.system_health.set(1.0)   # Sistema sano
            self.last_update_timestamp.set(datetime.now().timestamp())
            
            # Inicializar métricas de rentabilidad
            self.profit_total_usdt.labels(strategy="grid").set(0.0)
            self.profit_daily_usdt.labels(strategy="grid").set(0.0)
            self.profit_monthly_usdt.labels(strategy="grid").set(0.0)
            self.roi_total_percent.labels(strategy="grid").set(0.0)
            self.roi_daily_percent.labels(strategy="grid").set(0.0)
            
            logger.info("✅ Métricas inicializadas correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando métricas: {e}")
    
    async def update_all_metrics(self):
        """Actualiza todas las métricas del sistema"""
        try:
            logger.info("🔄 Actualizando métricas del sistema...")
            
            # Actualizar métricas de trading
            await self._update_trading_metrics()
            
            # Actualizar métricas de rentabilidad
            await self._update_profitability_metrics()
            
            # Actualizar métricas de portafolio
            await self._update_portfolio_metrics()
            
            # Actualizar métricas de rendimiento
            await self._update_performance_metrics()
            
            # Actualizar timestamp
            self.last_update_timestamp.set(datetime.now().timestamp())
            
            logger.info("✅ Todas las métricas actualizadas correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas: {e}")
            self.errors_total.labels(type="metrics_update").inc()
    
    async def _update_trading_metrics(self):
        """Actualiza métricas relacionadas con trading"""
        try:
            db = SessionLocal()
            
            # Total de trades por símbolo y lado
            trades_by_symbol_side = db.query(
                Trade.symbol, 
                Trade.side, 
                func.count(Trade.id).label('count')
            ).group_by(Trade.symbol, Trade.side).all()
            
            for symbol, side, count in trades_by_symbol_side:
                self.trades_total.labels(symbol=symbol, side=side).inc(count)
            
            # Trades de hoy
            today = datetime.now().date()
            today_trades = db.query(
                Trade.symbol, 
                Trade.side, 
                func.count(Trade.id).label('count')
            ).filter(
                func.date(Trade.timestamp) == today
            ).group_by(Trade.symbol, Trade.side).all()
            
            for symbol, side, count in today_trades:
                self.trades_daily.labels(symbol=symbol, side=side).inc(count)
            
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas de trading: {e}")
    
    async def _update_profitability_metrics(self):
        """Actualiza métricas de rentabilidad"""
        try:
            db = SessionLocal()
            
            # Ganancia total
            total_profit = db.query(func.sum(Trade.profit_loss)).filter(
                Trade.profit_loss.isnot(None)
            ).scalar() or 0.0
            
            self.profit_total_usdt.labels(strategy="grid").set(total_profit)
            
            # Ganancia diaria
            today = datetime.now().date()
            daily_profit = db.query(func.sum(Trade.profit_loss)).filter(
                and_(
                    func.date(Trade.timestamp) == today,
                    Trade.profit_loss.isnot(None)
                )
            ).scalar() or 0.0
            
            self.profit_daily_usdt.labels(strategy="grid").set(daily_profit)
            
            # Ganancia mensual
            month_start = datetime.now().replace(day=1).date()
            monthly_profit = db.query(func.sum(Trade.profit_loss)).filter(
                and_(
                    func.date(Trade.timestamp) >= month_start,
                    Trade.profit_loss.isnot(None)
                )
            ).scalar() or 0.0
            
            self.profit_monthly_usdt.labels(strategy="grid").set(monthly_profit)
            
            # Calcular ROI (simplificado)
            total_invested = db.query(func.sum(Trade.quantity * Trade.entry_price)).filter(
                Trade.side == 'BUY'
            ).scalar() or 1.0  # Evitar división por cero
            
            if total_invested > 0:
                roi_total = (total_profit / total_invested) * 100
                roi_daily = (daily_profit / total_invested) * 100
                
                self.roi_total_percent.labels(strategy="grid").set(roi_total)
                self.roi_daily_percent.labels(strategy="grid").set(roi_daily)
            
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas de rentabilidad: {e}")
    
    async def _update_portfolio_metrics(self):
        """Actualiza métricas del portafolio"""
        try:
            # Obtener balances actuales
            balances = binance_client_singleton.get_balances()
            
            total_value = 0.0
            
            for asset, amount in balances.items():
                if amount > 0:
                    # Actualizar balance del activo
                    self.portfolio_asset_balance.labels(asset=asset).set(amount)
                    
                    if asset == 'USDT':
                        asset_value = amount
                        total_value += asset_value
                    else:
                        try:
                            # Obtener precio actual
                            symbol = f"{asset}USDT"
                            price = binance_client_singleton.get_symbol_price(symbol)
                            asset_value = amount * price
                            total_value += asset_value
                            
                            # Actualizar valor del activo
                            self.portfolio_asset_value_usdt.labels(asset=asset).set(asset_value)
                            
                        except Exception as e:
                            logger.warning(f"No se pudo obtener precio para {asset}: {e}")
                            # Usar precio estimado
                            estimated_prices = {
                                'BTC': 114000,
                                'ETH': 3500,
                                'SPK': 0.1,
                                'BNB': 500
                            }
                            if asset in estimated_prices:
                                asset_value = amount * estimated_prices[asset]
                                total_value += asset_value
                                self.portfolio_asset_value_usdt.labels(asset=asset).set(asset_value)
            
            # Actualizar valor total del portafolio
            self.portfolio_total_value_usdt.set(total_value)
            
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas de portafolio: {e}")
    
    async def _update_performance_metrics(self):
        """Actualiza métricas de rendimiento"""
        try:
            db = SessionLocal()
            
            # Calcular tasa de éxito por símbolo
            symbols = db.query(Trade.symbol).distinct().all()
            
            for (symbol,) in symbols:
                total_trades = db.query(func.count(Trade.id)).filter(
                    Trade.symbol == symbol
                ).scalar()
                
                successful_trades = db.query(func.count(Trade.id)).filter(
                    and_(
                        Trade.symbol == symbol,
                        Trade.profit_loss.isnot(None),
                        Trade.profit_loss > 0
                    )
                ).scalar()
                
                if total_trades > 0:
                    success_rate = (successful_trades / total_trades) * 100
                    self.trade_success_rate.labels(symbol=symbol).set(success_rate)
            
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas de rendimiento: {e}")
    
    def record_trade_execution(self, symbol: str, side: str, quantity: float, price: float, execution_time: float = 0.0):
        """Registra la ejecución de un trade"""
        try:
            # Incrementar contadores
            self.trades_total.labels(symbol=symbol, side=side).inc()
            self.trades_daily.labels(symbol=symbol, side=side).inc()
            
            # Registrar volumen
            volume = quantity * price
            self.trade_volume_usdt.labels(symbol=symbol, side=side).inc(volume)
            
            # Registrar tiempo de ejecución
            if execution_time > 0:
                self.trade_execution_time.labels(symbol=symbol).observe(execution_time)
            
            # Registrar señal ejecutada
            self.signals_executed.labels(symbol=symbol, action=side).inc()
            
            logger.info(f"📊 Métricas de trade registradas: {side} {quantity} {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Error registrando métricas de trade: {e}")
    
    def record_signal_detected(self, symbol: str, action: str):
        """Registra una señal detectada"""
        try:
            self.signals_detected.labels(symbol=symbol, action=action).inc()
        except Exception as e:
            logger.error(f"❌ Error registrando señal: {e}")
    
    def record_error(self, error_type: str, service: str = "unknown"):
        """Registra un error"""
        try:
            self.errors_total.labels(type=error_type).inc()
            if service != "unknown":
                self.api_errors.labels(service=service).inc()
        except Exception as e:
            logger.error(f"❌ Error registrando error: {e}")
    
    def set_system_health(self, is_healthy: bool):
        """Establece el estado de salud del sistema"""
        try:
            self.system_health.set(1.0 if is_healthy else 0.0)
        except Exception as e:
            logger.error(f"❌ Error estableciendo salud del sistema: {e}")

# Instancia global del gestor de métricas
metrics_manager = MetricsManager() 