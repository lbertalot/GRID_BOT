#!/usr/bin/env python3
"""
Script de monitoreo avanzado para analizar el rendimiento del trading
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def monitor_trading_performance():
    """Monitorea el rendimiento del trading en tiempo real"""
    try:
        print("📊 Monitoreo Avanzado de Trading")
        print("=" * 50)
        
        from app.core.optimized_grid_manager import create_optimized_grid_manager
        from app.services.fund_manager import fund_manager
        
        # Crear manager
        manager = await create_optimized_grid_manager('grid_config_optimized.json')
        if not manager:
            print("❌ No se pudo crear el manager")
            return
        
        # Obtener datos actuales
        balances = await manager.get_asset_balances()
        prices = await manager.get_current_prices(['BTCUSDT', 'ETHUSDT', 'SPKUSDT'])
        
        print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Análisis de balances
        print("💰 ANÁLISIS DE BALANCES:")
        print("-" * 30)
        usdt_balance = balances.get('USDT', 0)
        btc_balance = balances.get('BTC', 0)
        eth_balance = balances.get('ETH', 0)
        spk_balance = balances.get('SPK', 0)
        
        print(f"USDT: ${usdt_balance:.2f}")
        print(f"BTC: {btc_balance:.6f}")
        print(f"ETH: {eth_balance:.6f}")
        print(f"SPK: {spk_balance:.2f}")
        
        # Calcular valor total del portafolio
        total_value = usdt_balance
        if btc_balance > 0 and 'BTCUSDT' in prices:
            total_value += btc_balance * prices['BTCUSDT']
        if eth_balance > 0 and 'ETHUSDT' in prices:
            total_value += eth_balance * prices['ETHUSDT']
        if spk_balance > 0 and 'SPKUSDT' in prices:
            total_value += spk_balance * prices['SPKUSDT']
        
        print(f"💼 Valor total del portafolio: ${total_value:.2f}")
        print()
        
        # Análisis de precios y señales
        print("📈 ANÁLISIS DE PRECIOS Y SEÑALES:")
        print("-" * 35)
        
        for symbol in ['BTCUSDT', 'ETHUSDT', 'SPKUSDT']:
            if symbol in prices:
                current_price = prices[symbol]
                asset_config = manager.config.assets.get(symbol)
                
                if asset_config and asset_config.is_active:
                    print(f"\n🪙 {symbol}:")
                    print(f"   Precio actual: ${current_price}")
                    print(f"   Rango de grilla: ${asset_config.min_price} - ${asset_config.max_price}")
                    print(f"   Niveles: {len(asset_config.grid_levels)}")
                    print(f"   Última acción: {asset_config.last_action or 'Ninguna'}")
                    
                    # Verificar si el precio está en rango
                    if current_price >= asset_config.min_price and current_price <= asset_config.max_price:
                        print(f"   ✅ Precio dentro del rango")
                        
                        # Encontrar nivel más cercano
                        closest_level = min(asset_config.grid_levels, key=lambda x: abs(x - current_price))
                        distance = abs(current_price - closest_level)
                        tolerance = (asset_config.max_price - asset_config.min_price) * 0.005
                        
                        print(f"   📍 Nivel más cercano: ${closest_level}")
                        print(f"   📏 Distancia al nivel: ${distance:.6f}")
                        print(f"   🎯 Tolerancia: ${tolerance:.6f}")
                        
                        if distance <= tolerance:
                            print(f"   🚨 ¡SEÑAL POTENCIAL DETECTADA!")
                            if current_price <= closest_level:
                                print(f"   📈 Señal de COMPRA en ${closest_level}")
                            else:
                                print(f"   📉 Señal de VENTA en ${closest_level}")
                        else:
                            print(f"   ⏳ Esperando cruce de nivel...")
                    else:
                        print(f"   ⚠️ Precio fuera del rango")
        
        # Análisis de capacidad de trading
        print(f"\n🔍 ANÁLISIS DE CAPACIDAD DE TRADING:")
        print("-" * 35)
        
        trading_summary = await fund_manager.get_trading_summary(balances)
        
        print(f"💰 Saldo USDT disponible: ${trading_summary.get('usdt_balance', 0):.2f}")
        print(f"🎯 Valor mínimo por operación: ${trading_summary.get('min_notional', 10):.2f}")
        print(f"📊 Máximo de operaciones posibles: {trading_summary.get('max_trades_possible', 0)}")
        print(f"✅ Puede operar: {'Sí' if trading_summary.get('can_trade', False) else 'No'}")
        
        # Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        print("-" * 20)
        
        if not trading_summary.get('can_trade', False):
            print("⚠️ Saldo insuficiente para operar")
            print("   - Considerar agregar más USDT")
            print("   - Revisar configuración de cantidades mínimas")
        else:
            print("✅ Sistema listo para operar")
            print("   - Saldos suficientes")
            print("   - Configuración válida")
        
        # Verificar si hay señales pendientes
        signals_detected = 0
        for symbol in ['BTCUSDT', 'ETHUSDT', 'SPKUSDT']:
            if symbol in prices:
                current_price = prices[symbol]
                asset_config = manager.config.assets.get(symbol)
                if asset_config and asset_config.is_active:
                    if current_price >= asset_config.min_price and current_price <= asset_config.max_price:
                        closest_level = min(asset_config.grid_levels, key=lambda x: abs(x - current_price))
                        distance = abs(current_price - closest_level)
                        tolerance = (asset_config.max_price - asset_config.min_price) * 0.005
                        if distance <= tolerance:
                            signals_detected += 1
        
        if signals_detected > 0:
            print(f"🚨 {signals_detected} señal(es) potencial(es) detectada(s)")
            print("   - Verificar logs para detalles")
            print("   - Monitorear próximos ciclos")
        else:
            print("⏳ Sin señales activas en este momento")
        
        print(f"\n📊 Resumen: Sistema {'OPERATIVO' if trading_summary.get('can_trade', False) else 'NO OPERATIVO'}")
        
    except Exception as e:
        print(f"❌ Error en monitoreo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(monitor_trading_performance()) 