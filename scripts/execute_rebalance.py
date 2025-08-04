#!/usr/bin/env python3
"""
Script para ejecutar rebalanceo automático
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer import auto_rebalancer

async def execute_rebalance():
    """Ejecuta el rebalanceo automático"""
    try:
        print("🔄 Iniciando rebalanceo automático...")
        
        # Verificar estado antes
        status_before = await auto_rebalancer.get_rebalance_status()
        print(f"\n📊 Estado antes del rebalanceo:")
        print(f"• Activos que necesitan rebalanceo: {status_before.get('assets_needing_rebalance', 0)}")
        print(f"• USDT total necesario: ${status_before.get('total_needed_usdt', 0):.2f}")
        print(f"• USDT disponible: ${status_before.get('available_usdt', 0):.2f}")
        
        if not status_before.get('can_rebalance', False):
            print("\n⚠️ No se puede rebalancear - USDT insuficiente")
            print("💡 Necesitas agregar al menos $45.00 USDT para activar todos los activos")
            return
        
        # Ejecutar rebalanceo
        result = await auto_rebalancer.check_and_rebalance()
        
        print(f"\n📈 Resultado del rebalanceo:")
        print(f"• Status: {result.get('status')}")
        print(f"• Mensaje: {result.get('message', 'N/A')}")
        
        if result.get('rebalance_results'):
            print("\n📋 Detalles de operaciones:")
            for op in result['rebalance_results']:
                print(f"• {op['symbol']}: {op['status']}")
                if op['status'] == 'success':
                    print(f"  - Cantidad: {op['quantity']:.6f}")
                    print(f"  - USDT gastado: ${op['usdt_spent']:.2f}")
                elif op['status'] == 'failed':
                    print(f"  - Razón: {op['reason']}")
        
        # Verificar estado después
        status_after = await auto_rebalancer.get_rebalance_status()
        print(f"\n📊 Estado después del rebalanceo:")
        print(f"• Activos que necesitan rebalanceo: {status_after.get('assets_needing_rebalance', 0)}")
        print(f"• USDT disponible: ${status_after.get('available_usdt', 0):.2f}")
        
        if status_after.get('assets_needing_rebalance', 0) == 0:
            print("\n✅ ¡Rebalanceo completado exitosamente!")
            print("🎯 Todos los activos están listos para operar")
        else:
            print("\n⚠️ Algunos activos aún necesitan rebalanceo")
            
    except Exception as e:
        print(f"❌ Error ejecutando rebalanceo: {e}")

if __name__ == "__main__":
    asyncio.run(execute_rebalance()) 