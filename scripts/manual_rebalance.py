#!/usr/bin/env python3
"""
Script para rebalanceo manual de un activo específico
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer import auto_rebalancer

async def manual_rebalance(symbol: str, usdt_amount: float):
    """Ejecuta rebalanceo manual para un símbolo específico"""
    try:
        print(f"🔄 Ejecutando rebalanceo manual para {symbol}: ${usdt_amount}")
        
        result = await auto_rebalancer.manual_rebalance(symbol, usdt_amount)
        
        print(f"\n📈 Resultado del rebalanceo manual:")
        print(f"• Status: {result.get('status')}")
        print(f"• Mensaje: {result.get('message', 'N/A')}")
        
        if result.get('status') == 'success':
            order_result = result.get('order_result', {})
            print(f"• Orden ID: {order_result.get('order_id', 'N/A')}")
            print(f"• Cantidad: {order_result.get('quantity', 0):.6f}")
            print(f"• Precio: ${order_result.get('price', 0):.6f}")
            print(f"• USDT gastado: ${order_result.get('usdt_amount', 0):.2f}")
            print("\n✅ Rebalanceo manual completado exitosamente")
        else:
            print(f"\n❌ Error en rebalanceo manual: {result.get('message')}")
            
    except Exception as e:
        print(f"❌ Error ejecutando rebalanceo manual: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python scripts/manual_rebalance.py <symbol> <usdt_amount>")
        print("Ejemplo: python scripts/manual_rebalance.py BTCUSDT 15.0")
        sys.exit(1)
    
    symbol = sys.argv[1]
    usdt_amount = float(sys.argv[2])
    
    asyncio.run(manual_rebalance(symbol, usdt_amount)) 