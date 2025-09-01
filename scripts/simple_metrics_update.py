#!/usr/bin/env python3
"""
Script simple para actualizar métricas de Prometheus
"""

import os
import sys
import time
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar métricas directamente
from app.core.metrics import (
    profit_total_usdt, profit_daily_usdt, portfolio_total_value_usdt,
    roi_daily_percent, profit_by_asset_usdt, roi_by_asset_percent,
    trades_executed_total, trades_success_rate, trades_successful_total,
    trades_failed_total, bot_status, bot_last_execution_timestamp,
    balance_by_asset, active_positions_count, trading_volume_usdt,
    grid_cycle_duration_seconds, bot_errors_total
)

def update_simple_metrics():
    """Actualiza métricas con valores simples"""
    try:
        print("🚀 Actualizando métricas simples...")
        
        # Valores de ejemplo basados en la operación real que vimos
        total_profit = 0.0  # Basado en la operación real
        daily_profit = 0.0
        portfolio_value = 116.75  # Valor real del portafolio
        total_trades = 1  # Basado en la operación real
        successful_trades = 1
        failed_trades = 0
        
        # Actualizar métricas de profit
        profit_total_usdt.labels(strategy="grid").set(total_profit)
        profit_daily_usdt.labels(strategy="grid").set(daily_profit)
        portfolio_total_value_usdt.labels(strategy="grid").set(portfolio_value)
        
        # ROI diario
        if portfolio_value > 0:
            roi_daily = (daily_profit / portfolio_value) * 100
            roi_daily_percent.labels(strategy="grid").set(roi_daily)
        
        # Métricas de trades
        trades_executed_total.labels(side="SELL", asset="BTCUSDT", strategy="grid").inc(1)
        
        if total_trades > 0:
            success_rate = successful_trades / total_trades
            trades_success_rate.labels(strategy="grid").set(success_rate)
        
        trades_successful_total.labels(asset="BTCUSDT", strategy="grid").inc(1)
        trades_failed_total.labels(asset="BTCUSDT", strategy="grid").inc(0)
        
        # Volumen de trading (basado en la operación real)
        volume = 0.0001 * 108257.62  # cantidad * precio
        trading_volume_usdt.labels(asset="BTCUSDT", strategy="grid").inc(volume)
        
        # Estado del bot
        bot_status.labels(strategy="grid").set(1)  # Activo
        bot_last_execution_timestamp.labels(strategy="grid").set(time.time())
        
        # Métricas por activo
        profit_by_asset_usdt.labels(asset="BTCUSDT", strategy="grid").set(0.0)
        roi_by_asset_percent.labels(asset="BTCUSDT", strategy="grid").set(0.0)
        
        # Duración del ciclo grid (sin labels)
        grid_cycle_duration_seconds.observe(20.0)
        
        print("✅ Métricas actualizadas exitosamente")
        print(f"📊 Resumen:")
        print(f"   Total profit: ${total_profit}")
        print(f"   Daily profit: ${daily_profit}")
        print(f"   Portfolio value: ${portfolio_value}")
        print(f"   Total trades: {total_trades}")
        print(f"   Success rate: {success_rate if total_trades > 0 else 0}")
        
    except Exception as e:
        print(f"❌ Error actualizando métricas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_simple_metrics()
