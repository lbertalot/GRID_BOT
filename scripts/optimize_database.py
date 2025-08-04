#!/usr/bin/env python3
"""
Script para optimizar la base de datos con índices y consultas eficientes
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def optimize_database():
    """Optimiza la base de datos con índices y configuraciones"""
    try:
        print("🔧 Optimizando Base de Datos")
        print("=" * 40)
        
        import asyncpg
        
        # Conectar a la base de datos
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@localhost:5432/gridbot"))
        
        print("✅ Conectado a la base de datos")
        
        # Crear índices para optimizar consultas
        indexes = [
            # Índice para consultas por símbolo
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
            
            # Índice para consultas por timestamp
            "CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)",
            
            # Índice compuesto para consultas por símbolo y timestamp
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp ON trades(symbol, timestamp)",
            
            # Índice para consultas por side (BUY/SELL)
            "CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)",
            
            # Índice para consultas de profit_loss
            "CREATE INDEX IF NOT EXISTS idx_trades_profit_loss ON trades(profit_loss) WHERE profit_loss IS NOT NULL",
            
            # Índice para consultas por símbolo y side
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol_side ON trades(symbol, side)",
            
            # Índice para consultas de trades completos (con exit_price)
            "CREATE INDEX IF NOT EXISTS idx_trades_exit_price ON trades(exit_price) WHERE exit_price IS NOT NULL"
        ]
        
        print("📊 Creando índices...")
        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
                print(f"✅ Índice creado: {index_sql.split('idx_')[1].split(' ')[0]}")
            except Exception as e:
                print(f"⚠️ Índice ya existe o error: {e}")
        
        # Analizar estadísticas de la base de datos
        print("\n📈 Analizando estadísticas...")
        await conn.execute("ANALYZE trades")
        print("✅ Estadísticas actualizadas")
        
        # Verificar índices creados
        print("\n🔍 Verificando índices creados:")
        indexes_info = await conn.fetch("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'trades'
            ORDER BY indexname
        """)
        
        for idx in indexes_info:
            print(f"   📋 {idx['indexname']}")
        
        # Verificar rendimiento de consultas
        print("\n⚡ Probando rendimiento de consultas...")
        
        # Consulta de prueba 1: Contar trades por símbolo
        start_time = asyncio.get_event_loop().time()
        result1 = await conn.fetch("SELECT symbol, COUNT(*) FROM trades GROUP BY symbol")
        time1 = asyncio.get_event_loop().time() - start_time
        print(f"   📊 Consulta por símbolo: {time1:.4f}s")
        
        # Consulta de prueba 2: Sumar profit_loss
        start_time = asyncio.get_event_loop().time()
        result2 = await conn.fetch("SELECT SUM(profit_loss) FROM trades WHERE profit_loss IS NOT NULL")
        time2 = asyncio.get_event_loop().time() - start_time
        print(f"   💰 Consulta profit_loss: {time2:.4f}s")
        
        # Consulta de prueba 3: Trades del día
        start_time = asyncio.get_event_loop().time()
        result3 = await conn.fetch("SELECT COUNT(*) FROM trades WHERE timestamp >= CURRENT_DATE")
        time3 = asyncio.get_event_loop().time() - start_time
        print(f"   📅 Consulta trades del día: {time3:.4f}s")
        
        await conn.close()
        
        print("\n🎉 Optimización de base de datos completada")
        print("📊 Los índices mejorarán significativamente el rendimiento de las consultas")
        
    except Exception as e:
        print(f"❌ Error optimizando base de datos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(optimize_database()) 