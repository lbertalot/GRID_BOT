#!/usr/bin/env python3
"""
Script para generar métricas de prueba para el dashboard de Grafana
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def generate_test_metrics():
    """Genera métricas de prueba para el dashboard"""
    try:
        print("📊 Generando métricas de prueba para el dashboard")
        print("=" * 50)
        
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
        print("💰 Configurando métricas de rentabilidad...")
        
        # Métricas de rentabilidad
        profit_total_usdt.labels(strategy="grid").set(125.50)  # $125.50 de ganancia total
        roi_daily_percent.labels(strategy="grid").set(2.35)    # 2.35% ROI diario
        profit_daily_usdt.labels(strategy="grid").set(15.75)   # $15.75 ganancia diaria
        portfolio_total_value_usdt.labels(strategy="grid").set(5340.25)  # $5,340.25 valor total
        
        # Métricas por activo
        print("📈 Configurando métricas por activo...")
        profit_by_asset_usdt.labels(asset="BTCUSDT", strategy="grid").set(45.20)
        profit_by_asset_usdt.labels(asset="ETHUSDT", strategy="grid").set(32.15)
        profit_by_asset_usdt.labels(asset="SPKUSDT", strategy="grid").set(48.15)
        
        roi_by_asset_percent.labels(asset="BTCUSDT", strategy="grid").set(3.2)
        roi_by_asset_percent.labels(asset="ETHUSDT", strategy="grid").set(2.8)
        roi_by_asset_percent.labels(asset="SPKUSDT", strategy="grid").set(4.1)
        
        # Métricas de trading
        print("🔄 Configurando métricas de trading...")
        trades_executed_total.labels(side="BUY", asset="BTCUSDT", strategy="grid").inc(15)
        trades_executed_total.labels(side="SELL", asset="BTCUSDT", strategy="grid").inc(12)
        trades_executed_total.labels(side="BUY", asset="ETHUSDT", strategy="grid").inc(18)
        trades_executed_total.labels(side="SELL", asset="ETHUSDT", strategy="grid").inc(16)
        trades_executed_total.labels(side="BUY", asset="SPKUSDT", strategy="grid").inc(22)
        trades_executed_total.labels(side="SELL", asset="SPKUSDT", strategy="grid").inc(20)
        
        trades_success_rate.labels(strategy="grid").set(0.92)  # 92% tasa de éxito
        
        # Estado del bot
        print("🤖 Configurando estado del bot...")
        bot_status.labels(strategy="grid").set(1)  # Bot activo
        bot_last_execution_timestamp.labels(strategy="grid").set(1733260800)  # Timestamp actual
        
        print("✅ Métricas de prueba generadas exitosamente")
        print("\n📊 Resumen de métricas:")
        print(f"   💰 Ganancia total: $125.50")
        print(f"   📈 ROI diario: 2.35%")
        print(f"   💵 Ganancia diaria: $15.75")
        print(f"   🏦 Valor del portafolio: $5,340.25")
        print(f"   🔄 Tasa de éxito: 92%")
        print(f"   🤖 Estado del bot: Activo")
        
        print("\n🌐 Verifica el dashboard en: http://localhost:3000")
        print("   Usuario: admin")
        print("   Contraseña: admin")
        
    except Exception as e:
        print(f"❌ Error generando métricas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(generate_test_metrics()) 