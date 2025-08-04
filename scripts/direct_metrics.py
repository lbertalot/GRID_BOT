#!/usr/bin/env python3
"""
Script para ejecutar métricas directamente en el proceso de la API
"""

import requests
import json

def execute_direct_metrics():
    """Ejecuta métricas directamente en la API"""
    try:
        print("🚀 Ejecutando métricas directamente en la API...")
        
        # Crear un script que se ejecute dentro del contenedor
        script_content = '''
import sys
import os
sys.path.append("/app")

from app.core.metrics import (
    profit_total_usdt,
    roi_daily_percent,
    profit_daily_usdt,
    portfolio_total_value_usdt,
    profit_by_asset_usdt,
    roi_by_asset_percent,
    trades_executed_total,
    trades_success_rate,
    bot_status,
    bot_last_execution_timestamp
)

# Generar métricas de prueba
profit_total_usdt.labels(strategy="grid").set(125.50)
roi_daily_percent.labels(strategy="grid").set(2.35)
profit_daily_usdt.labels(strategy="grid").set(15.75)
portfolio_total_value_usdt.labels(strategy="grid").set(5340.25)

profit_by_asset_usdt.labels(asset="BTCUSDT", strategy="grid").set(45.20)
profit_by_asset_usdt.labels(asset="ETHUSDT", strategy="grid").set(32.15)
profit_by_asset_usdt.labels(asset="SPKUSDT", strategy="grid").set(48.15)

roi_by_asset_percent.labels(asset="BTCUSDT", strategy="grid").set(3.2)
roi_by_asset_percent.labels(asset="ETHUSDT", strategy="grid").set(2.8)
roi_by_asset_percent.labels(asset="SPKUSDT", strategy="grid").set(4.1)

trades_executed_total.labels(side="BUY", asset="BTCUSDT", strategy="grid").inc(15)
trades_executed_total.labels(side="SELL", asset="BTCUSDT", strategy="grid").inc(12)
trades_executed_total.labels(side="BUY", asset="ETHUSDT", strategy="grid").inc(18)
trades_executed_total.labels(side="SELL", asset="ETHUSDT", strategy="grid").inc(16)
trades_executed_total.labels(side="BUY", asset="SPKUSDT", strategy="grid").inc(22)
trades_executed_total.labels(side="SELL", asset="SPKUSDT", strategy="grid").inc(20)

trades_success_rate.labels(strategy="grid").set(0.92)
bot_status.labels(strategy="grid").set(1)
bot_last_execution_timestamp.labels(strategy="grid").set(1733260800)

print("✅ Métricas generadas exitosamente")
'''
        
        # Guardar el script en el contenedor
        import subprocess
        result = subprocess.run([
            'docker', 'exec', 'gridbot_api', 'bash', '-c', 
            f'echo \'{script_content}\' > /app/direct_metrics.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Script guardado en el contenedor")
            
            # Ejecutar el script
            result = subprocess.run([
                'docker', 'exec', 'gridbot_api', 'python', '/app/direct_metrics.py'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Script ejecutado exitosamente")
                print(f"📄 Salida: {result.stdout}")
            else:
                print(f"❌ Error ejecutando script: {result.stderr}")
        else:
            print(f"❌ Error guardando script: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    execute_direct_metrics() 