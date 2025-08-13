"""
Métricas Prometheus para el dashboard de rentabilidad del bot de trading
Orientado a usuarios no técnicos
"""

from prometheus_client import Counter, Gauge, Histogram, Summary
from typing import Dict, Optional
import time
from datetime import datetime, timedelta

# ============================================================================
# MÉTRICAS DE RENTABILIDAD (Principales para el dashboard)
# ============================================================================

# Ganancia total acumulada en USDT
profit_total_usdt = Gauge(
    'profit_total_usdt',
    'Ganancia total acumulada en USDT',
    ['strategy']
)

# ROI diario en porcentaje
roi_daily_percent = Gauge(
    'roi_daily_percent',
    'ROI diario en porcentaje',
    ['strategy']
)

# Ganancia diaria en USDT
profit_daily_usdt = Gauge(
    'profit_daily_usdt',
    'Ganancia diaria en USDT',
    ['strategy']
)

# Valor total del portafolio en USDT
portfolio_total_value_usdt = Gauge(
    'portfolio_total_value_usdt',
    'Valor total del portafolio en USDT',
    ['strategy']
)

# Ganancia por activo específico
profit_by_asset_usdt = Gauge(
    'profit_by_asset_usdt',
    'Ganancia por activo en USDT',
    ['asset', 'strategy']
)

# ROI por activo específico
roi_by_asset_percent = Gauge(
    'roi_by_asset_percent',
    'ROI por activo en porcentaje',
    ['asset', 'strategy']
)

# ============================================================================
# MÉTRICAS DE OPERACIONES
# ============================================================================

# Total de trades ejecutados
trades_executed_total = Counter(
    'trades_executed_total',
    'Total de trades ejecutados',
    ['side', 'asset', 'strategy']
)

# Tasa de éxito de trades (0-1)
trades_success_rate = Gauge(
    'trades_success_rate',
    'Tasa de éxito de trades (0-1)',
    ['strategy']
)

# Trades exitosos vs fallidos
trades_successful_total = Counter(
    'trades_successful_total',
    'Total de trades exitosos',
    ['asset', 'strategy']
)

trades_failed_total = Counter(
    'trades_failed_total',
    'Total de trades fallidos',
    ['asset', 'strategy']
)

# ============================================================================
# MÉTRICAS DE ESTADO DEL BOT
# ============================================================================

# Timestamp de última ejecución
bot_last_execution_timestamp = Gauge(
    'bot_last_execution_timestamp',
    'Timestamp de la última ejecución del bot',
    ['strategy']
)

# Estado del bot (1=activo, 0=inactivo)
bot_status = Gauge(
    'bot_status',
    'Estado del bot (1=activo, 0=inactivo)',
    ['strategy']
)

# Errores del bot
bot_errors_total = Counter(
    'bot_errors_total',
    'Total de errores del bot',
    ['error_type', 'strategy']
)

# ============================================================================
# MÉTRICAS DE SALDOS Y POSICIONES
# ============================================================================

# Saldo por activo
balance_by_asset = Gauge(
    'balance_by_asset',
    'Saldo por activo',
    ['asset', 'strategy']
)

# Posiciones activas
active_positions_count = Gauge(
    'active_positions_count',
    'Número de posiciones activas',
    ['strategy']
)

# ============================================================================
# MÉTRICAS DE RENDIMIENTO
# ============================================================================

# Latencia de ejecución de trades
trade_execution_duration = Histogram(
    'trade_execution_duration_seconds',
    'Duración de ejecución de trades',
    ['asset', 'strategy'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Volumen de trading
trading_volume_usdt = Counter(
    'trading_volume_usdt',
    'Volumen total de trading en USDT',
    ['asset', 'strategy']
)

# Duración de ciclos grid (para medir performance de ciclos completos)
grid_cycle_duration_seconds = Histogram(
    'grid_cycle_duration_seconds',
    'Duración del ciclo grid en segundos',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# ============================================================================
# MÉTRICAS DE API
# ============================================================================

# Contador de requests de API
api_requests_total = Counter(
    'api_requests_total',
    'Total de requests de API',
    ['method', 'endpoint', 'status_code']
)

# Duración de requests de API
api_request_duration = Histogram(
    'api_request_duration_seconds',
    'Duración de requests de API',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def record_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """
    Registra una request de API para métricas
    """
    try:
        # Incrementar contador de requests
        api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        # Registrar duración
        api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
    except Exception as e:
        # Log del error pero no fallar la aplicación
        print(f"Error registrando métrica de API: {e}")

def get_metrics():
    """
    Obtiene todas las métricas en formato Prometheus
    """
    try:
        from prometheus_client import generate_latest
        return generate_latest()
    except Exception as e:
        print(f"Error generando métricas: {e}")
        return ""

def get_trading_metrics():
    """
    Obtiene métricas específicas de trading
    """
    try:
        return {
            "profit_total": profit_total_usdt._value.get(),
            "roi_daily": roi_daily_percent._value.get(),
            "portfolio_value": portfolio_total_value_usdt._value.get(),
            "trades_executed": trades_executed_total._value.get(),
            "success_rate": trades_success_rate._value.get()
        }
    except Exception as e:
        print(f"Error obteniendo métricas de trading: {e}")
        return {}

def get_binance_metrics():
    """
    Obtiene métricas de Binance
    """
    try:
        return {
            "api_requests": api_requests_total._value.get(),
            "api_duration_avg": api_request_duration._value.get()
        }
    except Exception as e:
        print(f"Error obteniendo métricas de Binance: {e}")
        return {}

def get_strategy_metrics():
    """
    Obtiene métricas de estrategias
    """
    try:
        return {
            "bot_status": bot_status._value.get(),
            "bot_errors": bot_errors_total._value.get(),
            "active_positions": active_positions_count._value.get()
        }
    except Exception as e:
        print(f"Error obteniendo métricas de estrategias: {e}")
        return {}

def record_order_execution(symbol: str, side: str, quantity: float, price: float, success: bool):
    """
    Registra la ejecución de una orden
    """
    try:
        volume_usdt = quantity * price
        trading_metrics.record_trade(
            side=side,
            asset=symbol,
            success=success,
            volume_usdt=volume_usdt,
            execution_time=0.1,  # Valor por defecto
            strategy="grid"
        )
    except Exception as e:
        print(f"Error registrando ejecución de orden: {e}")

def record_order_failure(symbol: str, side: str, error_type: str):
    """
    Registra el fallo de una orden
    """
    try:
        trading_metrics.record_error(error_type, "grid")
    except Exception as e:
        print(f"Error registrando fallo de orden: {e}")

def record_symbol_error(symbol: str, error_type: str):
    """
    Registra un error asociado a un símbolo específico.
    """
    try:
        # Para evitar crear demasiadas series, limitar error_type a un conjunto pequeño si se desea
        from prometheus_client import Counter
        # Registrar en un contador derivado del total de errores del bot por compatibilidad mínima
        bot_errors_total.labels(error_type=error_type, strategy="grid").inc()
    except Exception as e:
        print(f"Error registrando error por símbolo: {e}")

def update_balance(asset: str, free: float, locked: float):
    """
    Actualiza balance de un activo
    """
    try:
        balances = {asset: free + locked}
        trading_metrics.update_balances(balances, "grid")
    except Exception as e:
        print(f"Error actualizando balance: {e}")

def update_strategy_status(strategy_type: str, active_count: int):
    """
    Actualiza estado de estrategias
    """
    try:
        trading_metrics.update_active_positions(active_count, strategy_type)
    except Exception as e:
        print(f"Error actualizando estado de estrategia: {e}")

def update_profit_loss(total_profit: float, portfolio_value: float):
    """
    Actualiza métricas de P&L
    """
    try:
        trading_metrics.update_profit_metrics(total_profit, portfolio_value, "grid")
    except Exception as e:
        print(f"Error actualizando P&L: {e}")

# ============================================================================
# CLASE PARA GESTIONAR MÉTRICAS
# ============================================================================

class TradingMetrics:
    """
    Clase para gestionar todas las métricas del bot de trading
    """
    
    def __init__(self):
        self.last_update = time.time()
        self.daily_profit_start = 0.0
        self.daily_profit_current = 0.0
        self.portfolio_initial_value = 0.0
        
    def update_profit_metrics(self, 
                            total_profit: float,
                            portfolio_value: float,
                            strategy: str = "grid"):
        """
        Actualiza métricas de rentabilidad
        """
        # Ganancia total
        profit_total_usdt.labels(strategy=strategy).set(total_profit)
        
        # Valor del portafolio
        portfolio_total_value_usdt.labels(strategy=strategy).set(portfolio_value)
        
        # Calcular ganancia diaria
        current_time = time.time()
        if current_time - self.last_update > 86400:  # 24 horas
            self.daily_profit_start = self.daily_profit_current
            self.last_update = current_time
        
        daily_profit = total_profit - self.daily_profit_start
        profit_daily_usdt.labels(strategy=strategy).set(daily_profit)
        
        # Calcular ROI diario
        if self.portfolio_initial_value > 0:
            roi_daily = (daily_profit / self.portfolio_initial_value) * 100
            roi_daily_percent.labels(strategy=strategy).set(roi_daily)
    
    def update_asset_profit(self, 
                           asset: str,
                           profit: float,
                           roi: float,
                           strategy: str = "grid"):
        """
        Actualiza métricas por activo
        """
        profit_by_asset_usdt.labels(asset=asset, strategy=strategy).set(profit)
        roi_by_asset_percent.labels(asset=asset, strategy=strategy).set(roi)
    
    def record_trade(self, 
                    side: str,
                    asset: str,
                    success: bool,
                    volume_usdt: float,
                    execution_time: float,
                    strategy: str = "grid"):
        """
        Registra un trade ejecutado
        """
        # Incrementar contador total
        trades_executed_total.labels(side=side, asset=asset, strategy=strategy).inc()
        
        # Registrar éxito/fallo
        if success:
            trades_successful_total.labels(asset=asset, strategy=strategy).inc()
        else:
            trades_failed_total.labels(asset=asset, strategy=strategy).inc()
        
        # Actualizar tasa de éxito
        total_trades = trades_successful_total.labels(asset=asset, strategy=strategy)._value.get() + \
                      trades_failed_total.labels(asset=asset, strategy=strategy)._value.get()
        
        if total_trades > 0:
            success_rate = trades_successful_total.labels(asset=asset, strategy=strategy)._value.get() / total_trades
            trades_success_rate.labels(strategy=strategy).set(success_rate)
        
        # Registrar volumen
        trading_volume_usdt.labels(asset=asset, strategy=strategy).inc(volume_usdt)
        
        # Registrar duración de ejecución
        trade_execution_duration.labels(asset=asset, strategy=strategy).observe(execution_time)
    
    def update_bot_status(self, 
                         is_active: bool,
                         strategy: str = "grid"):
        """
        Actualiza estado del bot
        """
        status_value = 1 if is_active else 0
        bot_status.labels(strategy=strategy).set(status_value)
        
        if is_active:
            bot_last_execution_timestamp.labels(strategy=strategy).set(time.time())
    
    def record_error(self, 
                    error_type: str,
                    strategy: str = "grid"):
        """
        Registra un error del bot
        """
        bot_errors_total.labels(error_type=error_type, strategy=strategy).inc()
    
    def update_balances(self, 
                       balances: Dict[str, float],
                       strategy: str = "grid"):
        """
        Actualiza saldos por activo
        """
        for asset, balance in balances.items():
            balance_by_asset.labels(asset=asset, strategy=strategy).set(balance)
    
    def update_active_positions(self, 
                               count: int,
                               strategy: str = "grid"):
        """
        Actualiza número de posiciones activas
        """
        active_positions_count.labels(strategy=strategy).set(count)
    
    def set_initial_portfolio_value(self, value: float):
        """
        Establece el valor inicial del portafolio para cálculos de ROI
        """
        self.portfolio_initial_value = value

# Instancia global para usar en toda la aplicación
trading_metrics = TradingMetrics() 