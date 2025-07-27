#!/usr/bin/env python3
"""
Script para probar el AutoRebalancer
Verifica el estado actual y ejecuta rebalanceo si es necesario
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer import auto_rebalancer
from app.services.binance_client import BinanceClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_auto_rebalancer():
    """Prueba completa del AutoRebalancer"""
    
    print("🔄 Iniciando prueba del AutoRebalancer")
    print("=" * 50)
    
    try:
        # 1. Verificar estado actual
        print("\n📊 1. Verificando estado actual del rebalanceo...")
        status = await auto_rebalancer.get_rebalance_status()
        
        print(f"   - Activos que necesitan rebalanceo: {status.get('assets_needing_rebalance', 0)}")
        print(f"   - USDT disponible: ${status.get('available_usdt', 0):.2f}")
        print(f"   - USDT necesario: ${status.get('total_needed_usdt', 0):.2f}")
        print(f"   - Puede rebalancear: {status.get('can_rebalance', False)}")
        
        # Mostrar detalles de activos que necesitan rebalanceo
        rebalance_needs = status.get('rebalance_needs', [])
        if rebalance_needs:
            print("\n   📋 Activos que necesitan rebalanceo:")
            for need in rebalance_needs:
                symbol = need.get('symbol', 'Unknown')
                current_value = need.get('current_value_usdt', 0)
                needed_usdt = need.get('needed_usdt', 0)
                print(f"      - {symbol}: ${current_value:.2f} → +${needed_usdt:.2f}")
        
        # 2. Ejecutar rebalanceo automático
        print("\n🔄 2. Ejecutando rebalanceo automático...")
        result = await auto_rebalancer.check_and_rebalance()
        
        print(f"   - Estado: {result.get('status', 'unknown')}")
        
        if result.get('status') == 'success':
            rebalance_results = result.get('rebalance_results', [])
            successful = len([r for r in rebalance_results if r.get('status') == 'success'])
            failed = len([r for r in rebalance_results if r.get('status') != 'success'])
            
            print(f"   - Rebalanceos exitosos: {successful}")
            print(f"   - Rebalanceos fallidos: {failed}")
            
            if successful > 0:
                total_spent = sum(r.get('usdt_spent', 0) for r in rebalance_results if r.get('status') == 'success')
                print(f"   - Total invertido: ${total_spent:.2f} USDT")
                
                print("\n   📋 Detalles de rebalanceos:")
                for rebalance_result in rebalance_results:
                    symbol = rebalance_result.get('symbol', 'Unknown')
                    status = rebalance_result.get('status', 'unknown')
                    if status == 'success':
                        usdt_spent = rebalance_result.get('usdt_spent', 0)
                        print(f"      ✅ {symbol}: +${usdt_spent:.2f}")
                    else:
                        reason = rebalance_result.get('reason', 'Error desconocido')
                        print(f"      ❌ {symbol}: {reason}")
        
        elif result.get('status') == 'skipped':
            print("   - Rebalanceo saltado: ya en progreso")
        
        else:
            print(f"   - Error: {result.get('message', 'Error desconocido')}")
        
        # 3. Verificar estado después del rebalanceo
        print("\n📊 3. Verificando estado después del rebalanceo...")
        status_after = await auto_rebalancer.get_rebalance_status()
        
        print(f"   - Activos que necesitan rebalanceo: {status_after.get('assets_needing_rebalance', 0)}")
        print(f"   - USDT disponible: ${status_after.get('available_usdt', 0):.2f}")
        print(f"   - Puede rebalancear: {status_after.get('can_rebalance', False)}")
        
        # 4. Generar reporte final
        print("\n📋 4. Reporte final:")
        
        # Comparar estados
        assets_before = status.get('assets_needing_rebalance', 0)
        assets_after = status_after.get('assets_needing_rebalance', 0)
        improvement = assets_before - assets_after
        
        print(f"   - Activos operativos mejorados: {improvement}")
        print(f"   - Activos restantes por rebalancear: {assets_after}")
        
        if improvement > 0:
            print(f"   ✅ Rebalanceo exitoso: {improvement} activos activados")
        elif assets_after == 0:
            print("   ✅ Todos los activos están operativos")
        else:
            print(f"   ⚠️  Aún faltan {assets_after} activos por rebalancear")
        
        # 5. Guardar reporte
        report = {
            "timestamp": datetime.now().isoformat(),
            "status_before": status,
            "rebalance_result": result,
            "status_after": status_after,
            "improvement": improvement,
            "assets_remaining": assets_after
        }
        
        report_filename = f"rebalance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Reporte guardado en: {report_filename}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error en prueba del AutoRebalancer: {e}")
        print(f"❌ Error: {e}")
        return False


async def test_manual_rebalance():
    """Prueba de rebalanceo manual para un símbolo específico"""
    
    print("\n🔄 Prueba de rebalanceo manual")
    print("=" * 30)
    
    # Obtener símbolos que necesitan rebalanceo
    status = await auto_rebalancer.get_rebalance_status()
    rebalance_needs = status.get('rebalance_needs', [])
    
    if not rebalance_needs:
        print("   No hay activos que necesiten rebalanceo manual")
        return True
    
    # Tomar el primer activo que necesita rebalanceo
    need = rebalance_needs[0]
    symbol = need.get('symbol', 'BNBUSDT')
    needed_usdt = need.get('needed_usdt', 10.0)
    
    print(f"   Probando rebalanceo manual para {symbol}")
    print(f"   Cantidad a invertir: ${needed_usdt:.2f} USDT")
    
    try:
        result = await auto_rebalancer.manual_rebalance(symbol, needed_usdt)
        
        print(f"   - Estado: {result.get('status', 'unknown')}")
        
        if result.get('status') == 'success':
            order_result = result.get('order_result', {})
            print(f"   - Orden ID: {order_result.get('order_id', 'N/A')}")
            print(f"   - Cantidad: {order_result.get('quantity', 0):.6f}")
            print(f"   - USDT gastado: ${order_result.get('usdt_amount', 0):.2f}")
            print("   ✅ Rebalanceo manual exitoso")
        else:
            print(f"   ❌ Error: {result.get('message', 'Error desconocido')}")
        
        return result.get('status') == 'success'
        
    except Exception as e:
        logger.error(f"Error en rebalanceo manual: {e}")
        print(f"   ❌ Error: {e}")
        return False


async def main():
    """Función principal"""
    
    print("🚀 Iniciando pruebas del AutoRebalancer")
    print("=" * 60)
    
    # Verificar que el cliente de Binance esté disponible
    try:
        binance_client = BinanceClient()
        account_info = await binance_client.get_account_info()
        print(f"✅ Conexión a Binance establecida")
        print(f"   - Cuenta verificada: {account_info.get('permissions', [])}")
    except Exception as e:
        print(f"❌ Error conectando a Binance: {e}")
        return False
    
    # Ejecutar pruebas
    success = True
    
    # Prueba 1: Rebalanceo automático
    if not await test_auto_rebalancer():
        success = False
    
    # Prueba 2: Rebalanceo manual (opcional)
    if success:
        await test_manual_rebalance()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Todas las pruebas completadas exitosamente")
    else:
        print("❌ Algunas pruebas fallaron")
    
    return success


if __name__ == "__main__":
    # Ejecutar el script
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 