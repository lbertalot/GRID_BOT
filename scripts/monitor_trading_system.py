#!/usr/bin/env python3
"""
Script para monitorear el estado completo del sistema de trading
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer import auto_rebalancer
from app.services.binance_credentials import test_binance_connection

async def monitor_system():
    """Monitorea el estado completo del sistema"""
    try:
        print("🔍 Monitoreo del Sistema de Trading")
        print("=" * 50)
        print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. Verificar credenciales de Binance
        print("\n🔐 Verificando credenciales de Binance...")
        credentials_valid = test_binance_connection()
        print(f"✅ Credenciales: {'Válidas' if credentials_valid else 'Inválidas'}")
        
        # 2. Verificar estado del AutoRebalancer
        print("\n📊 Estado del AutoRebalancer...")
        rebalance_status = await auto_rebalancer.get_rebalance_status()
        
        print(f"• Activos que necesitan rebalanceo: {rebalance_status.get('assets_needing_rebalance', 0)}")
        print(f"• USDT total necesario: ${rebalance_status.get('total_needed_usdt', 0):.2f}")
        print(f"• USDT disponible: ${rebalance_status.get('available_usdt', 0):.2f}")
        print(f"• Puede rebalancear: {rebalance_status.get('can_rebalance', False)}")
        
        if rebalance_status.get('rebalance_needs'):
            print("\n📋 Detalles por activo:")
            for need in rebalance_status['rebalance_needs']:
                print(f"• {need['symbol']}: ${need['needed_usdt']:.2f} USDT")
                print(f"  - Balance actual: {need['current_balance']:.6f} {need['base_asset']}")
                print(f"  - Valor actual: ${need['current_value_usdt']:.2f}")
        
        # 3. Resumen del estado del sistema
        print("\n🎯 Resumen del Sistema:")
        
        if rebalance_status.get('assets_needing_rebalance', 0) == 0:
            print("✅ Sistema listo para operar - Todos los activos tienen saldo suficiente")
            print("🚀 El bot puede ejecutar operaciones de grid trading")
        else:
            print("⚠️ Sistema requiere configuración:")
            print(f"   • Necesitas agregar ${rebalance_status.get('total_needed_usdt', 0):.2f} USDT")
            print(f"   • O modificar la configuración para usar activos con saldo")
            print("\n💡 Opciones:")
            print("   1. Agregar USDT a tu cuenta Binance")
            print("   2. Ejecutar: python scripts/execute_rebalance.py")
            print("   3. Modificar grid_config_optimized.json para usar otros activos")
        
        # 4. Estado del modo Paper Trading
        import os
        paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"
        print(f"\n📄 Modo Paper Trading: {'Activado' if paper_trading else 'Desactivado'}")
        
        if paper_trading:
            print("✅ Operaciones se ejecutarán en modo simulación")
        else:
            print("⚠️ Operaciones se ejecutarán con dinero real")
            
    except Exception as e:
        print(f"❌ Error en monitoreo: {e}")

if __name__ == "__main__":
    asyncio.run(monitor_system()) 