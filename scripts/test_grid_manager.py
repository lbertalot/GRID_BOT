#!/usr/bin/env python3
"""
Script para probar el OptimizedGridManager directamente
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def test_grid_manager():
    """Prueba el OptimizedGridManager"""
    try:
        print("🧪 Probando OptimizedGridManager")
        print("=" * 40)
        
        from app.core.optimized_grid_manager import create_optimized_grid_manager
        
        # Crear el grid manager
        print("🔧 Creando OptimizedGridManager...")
        manager = await create_optimized_grid_manager('grid_config_optimized.json')
        
        if not manager:
            print("❌ Error creando OptimizedGridManager")
            return
        
        print("✅ OptimizedGridManager creado exitosamente")
        
        # Verificar cliente Binance
        print("\n🔐 Verificando cliente Binance...")
        if not manager.client:
            print("❌ Cliente Binance no inicializado")
            return
        
        if not hasattr(manager.client, 'api_key') or not manager.client.api_key:
            print("❌ Cliente Binance sin credenciales válidas")
            return
        
        print(f"✅ Cliente Binance inicializado - API Key: {manager.client.api_key[:10]}...")
        
        # Obtener balances
        print("\n💰 Obteniendo balances...")
        balances = await manager.get_asset_balances()
        
        if not balances:
            print("❌ No se pudieron obtener balances")
            return
        
        print(f"✅ Balances obtenidos: {len(balances)} activos")
        for asset, balance in balances.items():
            if balance > 0:
                print(f"   • {asset}: {balance}")
        
        # Obtener precios
        print("\n📊 Obteniendo precios...")
        symbols = [asset.symbol for asset in manager.config.assets.values() if asset.is_active]
        prices = await manager.get_current_prices(symbols)
        
        if not prices:
            print("❌ No se pudieron obtener precios")
            return
        
        print(f"✅ Precios obtenidos: {len(prices)} símbolos")
        for symbol, price in prices.items():
            print(f"   • {symbol}: ${price}")
        
        # Calcular cantidades óptimas
        print("\n🎯 Calculando cantidades óptimas...")
        optimal_quantities = manager.calculate_optimal_quantities(balances, prices)
        
        print(f"✅ Cantidades calculadas: {len(optimal_quantities)} activos")
        for symbol, quantity in optimal_quantities.items():
            print(f"   • {symbol}: {quantity}")
        
        # Verificar activos con saldo insuficiente
        if manager.insufficient_funds:
            print(f"\n⚠️ Activos con saldo insuficiente: {len(manager.insufficient_funds)}")
            for symbol, info in manager.insufficient_funds.items():
                print(f"   • {symbol}: Faltan {info['faltante']} {symbol.replace('USDT', '')}")
        else:
            print("\n✅ Todos los activos tienen saldo suficiente")
        
        print("\n🎉 OptimizedGridManager funcionando correctamente!")
        
    except Exception as e:
        print(f"❌ Error probando OptimizedGridManager: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_grid_manager()) 