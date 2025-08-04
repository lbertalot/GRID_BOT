#!/usr/bin/env python3
"""
Script para poblar la tabla asset_limits con datos de Binance
Obtiene los límites de trading de todos los símbolos disponibles
"""

import os
import sys
import asyncio
import asyncpg
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

async def populate_asset_limits():
    """Pobla la tabla asset_limits con datos de Binance"""
    
    print("🚀 Poblando tabla asset_limits con datos de Binance...")
    print("=" * 60)
    
    # Configuración
    database_url = os.getenv('DATABASE_URL', 'postgresql://griduser:gridpass@localhost:5432/gridbot')
    api_key = os.getenv('BINANCE_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY')
    testnet = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
    
    print(f"📊 Configuración:")
    print(f"   • Database URL: {database_url}")
    print(f"   • API Key: {'✅ Configurada' if api_key else '❌ No configurada'}")
    print(f"   • Secret Key: {'✅ Configurada' if secret_key else '❌ No configurada'}")
    print(f"   • Testnet: {'✅ Activado' if testnet else '❌ Desactivado'}")
    
    if not api_key or not secret_key:
        print("❌ Error: Credenciales de Binance no configuradas")
        return False
    
    try:
        # Conectar a la base de datos
        print("\n🔗 Conectando a la base de datos...")
        conn = await asyncpg.connect(database_url)
        print("✅ Conexión a base de datos establecida")
        
        # Crear cliente de Binance
        print("\n🔗 Conectando a Binance...")
        if testnet:
            client = Client(api_key, secret_key, testnet=True)
            print("✅ Conectado a Binance Testnet")
        else:
            client = Client(api_key, secret_key)
            print("✅ Conectado a Binance Mainnet")
        
        # Obtener información del exchange
        print("\n📊 Obteniendo información del exchange...")
        exchange_info = client.get_exchange_info()
        symbols = exchange_info['symbols']
        
        # Filtrar símbolos que están en trading
        trading_symbols = [s for s in symbols if s['status'] == 'TRADING']
        print(f"✅ Símbolos en trading: {len(trading_symbols)}")
        
        # Limpiar tabla existente
        print("\n🧹 Limpiando tabla asset_limits...")
        await conn.execute("DELETE FROM asset_limits")
        print("✅ Tabla limpiada")
        
        # Insertar límites de activos
        print("\n📋 Insertando límites de activos...")
        inserted_count = 0
        
        for symbol_info in trading_symbols:
            symbol = symbol_info['symbol']
            
            # Obtener filtros de lot size y price
            lot_size_filter = None
            price_filter = None
            
            for filter_info in symbol_info['filters']:
                if filter_info['filterType'] == 'LOT_SIZE':
                    lot_size_filter = filter_info
                elif filter_info['filterType'] == 'PRICE_FILTER':
                    price_filter = filter_info
            
            if lot_size_filter and price_filter:
                try:
                    # Insertar en la base de datos
                    await conn.execute("""
                        INSERT INTO asset_limits (
                            symbol, min_price, max_price, tick_size, 
                            min_qty, max_qty, step_size, min_notional
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, 
                    symbol,
                    float(price_filter.get('minPrice', 0)),
                    float(price_filter.get('maxPrice', 999999)),
                    float(price_filter.get('tickSize', 0.00000001)),
                    float(lot_size_filter.get('minQty', 0)),
                    float(lot_size_filter.get('maxQty', 999999)),
                    float(lot_size_filter.get('stepSize', 0.00000001)),
                    10.0  # min_notional por defecto
                    )
                    
                    inserted_count += 1
                    
                    if inserted_count % 100 == 0:
                        print(f"   📊 Insertados: {inserted_count} símbolos")
                        
                except Exception as e:
                    print(f"   ⚠️  Error insertando {symbol}: {e}")
        
        print(f"\n✅ Proceso completado:")
        print(f"   • Símbolos procesados: {len(trading_symbols)}")
        print(f"   • Símbolos insertados: {inserted_count}")
        
        # Verificar inserción
        count = await conn.fetchval("SELECT COUNT(*) FROM asset_limits")
        print(f"   • Total en base de datos: {count}")
        
        # Mostrar algunos ejemplos
        print(f"\n📋 Ejemplos de límites insertados:")
        examples = await conn.fetch("""
            SELECT symbol, min_qty, max_qty, step_size, tick_size 
            FROM asset_limits 
            WHERE symbol IN ('BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT')
            ORDER BY symbol
        """)
        
        for example in examples:
            print(f"   • {example['symbol']}: min_qty={example['min_qty']}, step_size={example['step_size']}")
        
        await conn.close()
        return True
        
    except BinanceAPIException as e:
        print(f"❌ Error de API de Binance: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

async def verify_asset_limits():
    """Verifica que los límites se hayan insertado correctamente"""
    
    print("\n🔍 Verificando límites de activos...")
    print("=" * 40)
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://griduser:gridpass@localhost:5432/gridbot')
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Verificar total
        total = await conn.fetchval("SELECT COUNT(*) FROM asset_limits")
        print(f"📊 Total de límites: {total}")
        
        # Verificar símbolos específicos
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT']
        for symbol in test_symbols:
            row = await conn.fetchrow("""
                SELECT symbol, min_qty, max_qty, step_size, tick_size 
                FROM asset_limits 
                WHERE symbol = $1
            """, symbol)
            
            if row:
                print(f"✅ {symbol}: min_qty={row['min_qty']}, step_size={row['step_size']}")
            else:
                print(f"❌ {symbol}: No encontrado")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando límites: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Poblado de límites de activos - Grid Trading Bot")
    print("=" * 60)
    
    # Poblar límites
    if asyncio.run(populate_asset_limits()):
        print("\n🎉 ¡Límites de activos poblados exitosamente!")
        
        # Verificar
        asyncio.run(verify_asset_limits())
    else:
        print("\n❌ Falló el poblado de límites de activos")
        sys.exit(1) 