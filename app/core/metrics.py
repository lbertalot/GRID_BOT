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

# ROI total en porcentaje
roi_total_percent = Gauge(
    'roi_total_percent',
    'ROI total en porcentaje',
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

# Cambio del portafolio vs baseline en USDT
portfolio_change_usdt = Gauge(
    'portfolio_change_usdt',
    'Cambio del portafolio vs baseline en USDT',
    ['strategy']
)

# Saldo efectivo USDT
cash_balance_usdt = Gauge(
    'cash_balance_usdt',
    'Saldo efectivo en USDT (caja)',
    ['strategy']
)

# Breakers activos (cantidad)
active_breakers_total = Gauge(
    'active_breakers_total',
    'Cantidad de circuit breakers activos'
)

# Estado de breakers (0/1) por tipo
breaker_state = Gauge(
    'breaker_state',
    'Estado de breaker (0 inactivo, 1 activo)',
    ['type']
)

# Scores de integridad por componente
integrity_score = Gauge(
    'integrity_score',
    'Score de integridad (0-100) por componente',
    ['component']
)

# =========================================================================
# MÉTRICAS DE POLVO (DUST)
# =========================================================================

dust_assets_count = Gauge(
    'dust_assets_count',
    'Cantidad de activos con valor < 1 USDT'
)

dust_value_usd = Gauge(
    'dust_value_usd',
    'Suma de valor (USDT) de activos < 1 USDT'
)

dust_swept_usd_total = Counter(
    'dust_swept_usd_total',
    'Valor total (USDT) barrido (vendido/convertido) como polvo'
)

last_dust_sweep_timestamp = Gauge(
    'last_dust_sweep_timestamp',
    'Timestamp unix del último barrido de polvo'
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

# Métrica requerida por tests: gridbot_profit_loss (gauge simple)
gridbot_profit_loss = Gauge(
    'gridbot_profit_loss',
    'PnL agregado de GridBot en USDT',
)

# ============================================================================
# MÉTRICAS DE OPERACIONES
# ============================================================================

# Prefijo gridbot_* requerido por tests
gridbot_orders_total = Counter(
    'gridbot_orders_total',
    'Total de órdenes procesadas por GridBot',
    ['side', 'asset', 'strategy']
)

# Tasa de éxito de trades (0-1)
trades_success_rate = Gauge(
    'trades_success_rate',
    'Tasa de éxito de trades (0-1)',
    ['strategy']
)

# Total de trades ejecutados
trades_executed_total = Counter(
    'trades_executed_total',
    'Total de trades ejecutados',
    ['side', 'asset', 'strategy']
)

# Métricas de reconciliación
reconciliation_discrepancies_total = Counter(
    'reconciliation_discrepancies_total',
    'Total de discrepancias de reconciliación detectadas',
    ['type']
)

reconciliation_accuracy_percent = Gauge(
    'reconciliation_accuracy_percent',
    'Precisión de reconciliación en porcentaje (0-100)'
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

# Errores externos (e.g., Binance auth/network)
external_auth_failures = Counter(
    'external_auth_failures_total',
    'Total de fallos de autenticación/permiso con proveedores externos',
    ['provider', 'reason']
)

commission_update_failures = Counter(
    'commission_update_failures_total',
    'Total de fallos al actualizar comisiones externas',
    ['provider', 'reason']
)

# Errores de API de Binance (códigos y fase)
binance_api_errors_total = Counter(
    'binance_api_errors_total',
    'Total de errores de API de Binance',
    ['code', 'phase']
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

# Volumen de trading con prefijo requerido por tests
gridbot_volume_total = Counter(
    'gridbot_volume_total',
    'Volumen total de trading en USDT',
    ['asset', 'strategy']
)

# Latencia de ejecución de trades
trade_execution_duration = Histogram(
    'trade_execution_duration_seconds',
    'Duración de ejecución de trades',
    ['asset', 'strategy'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Duración de ciclos grid (para medir performance de ciclos completos)

grid_cycle_duration_seconds = Histogram(
    'grid_cycle_duration_seconds',
    'Duración del ciclo grid en segundos',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# ============================================================================
# MÉTRICAS DE CICLOS (Evaluación/Ejecución 5m)
# ============================================================================

# Fase actual del ciclo (valor = timestamp unix)
cycle_phase = Gauge(
    'cycle_phase_timestamp',
    'Timestamp de la fase actual del ciclo (evaluation/execution)',
    ['phase']
)

# Decisión lista al minuto 4 (valor = timestamp unix)
cycle_decision_ready = Gauge(
    'cycle_decision_ready',
    'Decisión de ciclo lista (minuto 4)',
    ['symbol', 'strategy']
)

# Orden ejecutada al minuto 5 (valor = timestamp unix)
cycle_order_executed = Gauge(
    'cycle_order_executed',
    'Orden ejecutada en el ciclo (minuto 5)',
    ['symbol', 'status']
)

# ============================================================================
# MÉTRICAS DE API
# ============================================================================

# Contador de requests de API con prefijo requerido
gridbot_api_requests_total = Counter(
    'gridbot_api_requests_total',
    'Total de requests de API',
    ['method', 'endpoint', 'status_code']
)

# Rechazos de validación de órdenes
order_validation_rejects_total = Counter(
    'order_validation_rejects_total',
    'Total de rechazos de validación de órdenes',
    ['reason', 'symbol']
)

# Reconciliación e integridad
reconciliation_latency_seconds = Histogram(
    'reconciliation_latency_seconds',
    'Tiempo de ejecución del ciclo de reconciliación',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

balance_discrepancy_usd = Gauge(
    'balance_discrepancy_usd',
    'Discrepancia absoluta de balance entre sistema y Binance en USD'
)

unaccounted_pnl_usd = Gauge(
    'unaccounted_pnl_usd',
    'PnL no contabilizado detectado en reconciliación en USD'
)

partial_fills_total = Counter(
    'partial_fills_total',
    'Total de órdenes parcialmente llenadas'
)

order_api_failures_total = Counter(
    'order_api_failures_total',
    'Fallos de API al enviar/consultar órdenes',
    ['reason']
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
        gridbot_api_requests_total.labels(
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
            # Notar: usamos contadores gridbot_* en tests
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
            "api_requests": gridbot_api_requests_total._value.get(),
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


def record_order_execution(symbol: str, side: str, order_type: str, strategy: str, quantity: float, price: float):
    """
    Registra la ejecución de una orden
    """
    try:
        volume_usdt = quantity * price
        gridbot_orders_total.labels(side=side, asset=symbol, strategy=strategy).inc()
        gridbot_volume_total.labels(asset=symbol, strategy=strategy).inc(volume_usdt)
    except Exception as e:
        print(f"Error registrando ejecución de orden: {e}")


def record_order_failure(symbol: str, side: str, order_type: str, error_type: str):
    """
    Registra el fallo de una orden
    """
    try:
        trades_failed_total.labels(asset=symbol, strategy="grid").inc()
        bot_errors_total.labels(error_type=error_type, strategy="grid").inc()
    except Exception as e:
        print(f"Error registrando fallo de orden: {e}")


def compute_win_loss_and_sharpe(trades: list[dict]) -> dict:
    """Calcula win/loss ratio y Sharpe simple a partir de trades con profit_loss.
    Retorna dict con 'win_ratio' y 'sharpe'.
    """
    if not trades:
        return {"win_ratio": 0.0, "sharpe": 0.0}
    profits = [float(t.get('profit_loss', 0.0) or 0.0) for t in trades]
    wins = sum(1 for p in profits if p > 0)
    total = len(profits)
    win_ratio = wins / total if total > 0 else 0.0
    mean = sum(profits) / total
    var = sum((p - mean) ** 2 for p in profits) / total
    std = var ** 0.5
    sharpe = (mean / std) if std > 0 else 0.0
    return {"win_ratio": win_ratio, "sharpe": sharpe}


def record_symbol_error(symbol: str, error_type: str):
    """
    Registra un error asociado a un símbolo específico.
    """
    try:
        from prometheus_client import Counter
        bot_errors_total.labels(error_type=error_type, strategy="grid").inc()
    except Exception as e:
        print(f"Error registrando error por símbolo: {e}")

# Contador de símbolos inválidos detectados
invalid_symbol_total = Counter(
    'invalid_symbol_total',
    'Total de ocurrencias de símbolo inválido normalizado',
    ['symbol']
)


def update_balance(asset: str, free: float, locked: float):
    """
    Actualiza balance de un activo
    """
    try:
        balances = {asset: free + locked}
        from app.core.metrics import trading_metrics  # evitar import circular
        trading_metrics.update_balances(balances, "grid")
    except Exception as e:
        print(f"Error actualizando balance: {e}")


def update_strategy_status(strategy_type: str, active_count: int):
    """
    Actualiza estado de estrategias
    """
    try:
        from app.core.metrics import trading_metrics
        trading_metrics.update_active_positions(active_count, strategy_type)
    except Exception as e:
        print(f"Error actualizando estado de estrategia: {e}")


def update_profit_loss(symbol: str, strategy: str, pnl: float):
    """
    Actualiza métricas de P&L por símbolo/estrategia y totales aproximados
    """
    try:
        profit_by_asset_usdt.labels(asset=symbol, strategy=strategy).inc(pnl)
        profit_total_usdt.labels(strategy=strategy).inc(pnl)
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
        # Referencias a métricas globales
        self.trades_success_rate = trades_success_rate
        self.trades_executed_total = trades_executed_total
    
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
        gridbot_volume_total.labels(asset=asset, strategy=strategy).inc(volume_usdt)
        
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