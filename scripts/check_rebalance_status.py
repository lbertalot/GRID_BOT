#!/usr/bin/env python3
"""
Script para verificar el estado del AutoRebalancer
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer import auto_rebalancer

async def check_status():
    """Verifica el estado del AutoRebalancer"""
    try:
        print("🔄 Verificando estado del AutoRebalancer...")
        status = await auto_rebalancer.get_rebalance_status()
        
        print("\n📊 Estado del AutoRebalancer:")
        print(f"• Activos que necesitan rebalanceo: {status.get('assets_needing_rebalance', 0)}")
        print(f"• USDT total necesario: ${status.get('total_needed_usdt', 0):.2f}")
        print(f"• USDT disponible: ${status.get('available_usdt', 0):.2f}")
        print(f"• Puede rebalancear: {status.get('can_rebalance', False)}")
        print(f"• Rebalanceo en progreso: {status.get('is_rebalancing', False)}")
        
        if status.get('rebalance_needs'):
            print("\n📋 Detalles por activo:")
            for need in status['rebalance_needs']:
                print(f"• {need['symbol']}: ${need['needed_usdt']:.2f} USDT")
                print(f"  - Balance actual: {need['current_balance']:.6f} {need['base_asset']}")
                print(f"  - Valor actual: ${need['current_value_usdt']:.2f}")
                print(f"  - Cantidad necesaria: {need['needed_quantity']:.6f}")
        else:
            print("\n✅ Todos los activos tienen saldo suficiente")
            
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")

if __name__ == "__main__":
    asyncio.run(check_status()) 