#!/usr/bin/env python3
"""
Script para probar señales de trading y forzar operaciones
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def test_trading_signals():
    """Prueba las señales de trading y fuerza operaciones si es necesario"""
    try:
        print("🧪 Probando Señales de Trading")
        print("=" * 40)
        
        from app.core.optimized_grid_manager import create_optimized_grid_manager
        from app.services.grid_strategy import decide_grid_action
        
        # Crear el grid manager
        print("🔧 Creando OptimizedGridManager...")
        manager = await create_optimized_grid_manager('grid_config_optimized.json')
        
        if not manager:
            print("❌ Error creando OptimizedGridManager")
            return
        
        print("✅ OptimizedGridManager creado exitosamente")
        
        # Obtener balances y precios
        print("\n💰 Obteniendo balances y precios...")
        balances = await manager.get_asset_balances()
        symbols = [asset.symbol for asset in manager.config.assets.values() if asset.is_active]
        prices = await manager.get_current_prices(symbols)
        
        print(f"✅ Balances: {len(balances)} activos")
        print(f"✅ Precios: {len(prices)} símbolos")
        
        # Analizar cada símbolo configurado
        print("\n🔍 Analizando señales de trading por símbolo:")
        print("-" * 50)
        
        for symbol in symbols:
            asset_config = manager.config.assets.get(symbol)
            if not asset_config:
                print(f"❌ {symbol}: Configuración no encontrada")
                continue
            
            current_price = prices.get(symbol, 0)
            if current_price <= 0:
                print(f"❌ {symbol}: Precio inválido (${current_price})")
                continue
            
            # Verificar balance
            base_asset = symbol.replace("USDT", "")
            balance = balances.get(base_asset, 0)
            
            print(f"\n📊 {symbol}:")
            print(f"   💰 Precio actual: ${current_price}")
            print(f"   💎 Balance {base_asset}: {balance}")
            print(f"   📈 Niveles de grilla: {asset_config.grid_levels}")
            print(f"   🔄 Última acción: {asset_config.last_action}")
            
            # Probar señal de trading
            action = decide_grid_action(current_price, asset_config.grid_levels, asset_config.last_action)
            
            if action and action.get("action"):
                print(f"   ✅ Señal detectada: {action['action']} en nivel {action.get('level', 'N/A')}")
                
                # Verificar si se puede ejecutar
                quantity = asset_config.quantity
                notional_value = quantity * current_price
                min_notional = manager.config.min_notional_threshold
                
                print(f"   📏 Cantidad configurada: {quantity}")
                print(f"   💵 Valor nocional: ${notional_value:.4f}")
                print(f"   🎯 Mínimo requerido: ${min_notional}")
                
                if notional_value >= min_notional:
                    if action["action"] == "SELL" and quantity > balance:
                        print(f"   ⛔ No se puede vender: saldo insuficiente")
                    else:
                        print(f"   🚀 ¡Listo para ejecutar {action['action']}!")
                else:
                    print(f"   ⛔ Valor nocional insuficiente")
            else:
                print(f"   ⛔ Sin señal de trading")
                
                # Análisis detallado
                if asset_config.grid_levels:
                    min_level = min(asset_config.grid_levels)
                    max_level = max(asset_config.grid_levels)
                    print(f"   📋 Rango de grilla: ${min_level} - ${max_level}")
                    
                    if current_price < min_level:
                        print(f"   ⬇️ Precio por debajo del rango mínimo")
                    elif current_price > max_level:
                        print(f"   ⬆️ Precio por encima del rango máximo")
                    else:
                        print(f"   ↔️ Precio dentro del rango, pero no cruzó niveles")
        
        # Forzar una operación de prueba si es necesario
        print("\n🧪 ¿Deseas forzar una operación de prueba? (s/n): ", end="")
        response = input().lower().strip()
        
        if response == 's':
            print("\n🚀 Forzando operación de prueba...")
            
            # Seleccionar el primer símbolo disponible
            test_symbol = None
            for symbol in symbols:
                asset_config = manager.config.assets.get(symbol)
                if asset_config and prices.get(symbol, 0) > 0:
                    test_symbol = symbol
                    break
            
            if test_symbol:
                print(f"📊 Usando {test_symbol} para operación de prueba")
                
                # Forzar una señal de compra
                asset_config = manager.config.assets.get(test_symbol)
                current_price = prices.get(test_symbol, 0)
                
                # Crear una señal forzada
                forced_action = {"action": "BUY", "level": current_price}
                
                print(f"🔧 Forzando señal: {forced_action}")
                
                # Ejecutar trade
                result = await manager._execute_trade(
                    symbol=test_symbol,
                    action=forced_action["action"],
                    quantity=asset_config.quantity,
                    price=current_price
                )
                
                if result:
                    print(f"✅ Operación de prueba ejecutada exitosamente")
                    print(f"   📋 Order ID: {result.order_id}")
                    print(f"   💰 Precio: ${result.price}")
                    print(f"   📏 Cantidad: {result.quantity}")
                else:
                    print(f"❌ Error ejecutando operación de prueba")
            else:
                print("❌ No hay símbolos disponibles para operación de prueba")
        
        print("\n🎉 Análisis de señales completado")
        
    except Exception as e:
        print(f"❌ Error en análisis de señales: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_trading_signals()) 