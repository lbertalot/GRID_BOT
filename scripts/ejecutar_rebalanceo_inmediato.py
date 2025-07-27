#!/usr/bin/env python3
"""
Script para ejecutar rebalanceo inmediato
Resuelve el problema de saldos insuficientes identificado en el análisis
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
from app.services.telegram_alert import send_telegram_alert

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def ejecutar_rebalanceo_inmediato():
    """Ejecuta rebalanceo inmediato para resolver saldos insuficientes"""
    
    print("🚀 Ejecutando rebalanceo inmediato")
    print("=" * 50)
    
    try:
        # 1. Verificar estado actual
        print("\n📊 Verificando estado actual...")
        status = await auto_rebalancer.get_rebalance_status()
        
        assets_needing = status.get('assets_needing_rebalance', 0)
        available_usdt = status.get('available_usdt', 0)
        needed_usdt = status.get('total_needed_usdt', 0)
        
        print(f"   - Activos que necesitan rebalanceo: {assets_needing}")
        print(f"   - USDT disponible: ${available_usdt:.2f}")
        print(f"   - USDT necesario: ${needed_usdt:.2f}")
        
        if assets_needing == 0:
            print("   ✅ Todos los activos están operativos")
            return True
        
        if available_usdt < needed_usdt:
            print(f"   ⚠️  USDT insuficiente. Necesario: ${needed_usdt:.2f}, Disponible: ${available_usdt:.2f}")
            print(f"   💡 Se ejecutará rebalanceo parcial con el USDT disponible")
        
        # 2. Ejecutar rebalanceo
        print(f"\n🔄 Ejecutando rebalanceo automático...")
        result = await auto_rebalancer.check_and_rebalance()
        
        if result.get('status') == 'success':
            rebalance_results = result.get('rebalance_results', [])
            successful = len([r for r in rebalance_results if r.get('status') == 'success'])
            failed = len([r for r in rebalance_results if r.get('status') != 'success'])
            
            print(f"   ✅ Rebalanceo completado:")
            print(f"      - Exitosos: {successful}")
            print(f"      - Fallidos: {failed}")
            
            if successful > 0:
                total_spent = sum(r.get('usdt_spent', 0) for r in rebalance_results if r.get('status') == 'success')
                print(f"      - Total invertido: ${total_spent:.2f} USDT")
                
                # Mostrar detalles
                print(f"\n   📋 Detalles de rebalanceos:")
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
            print("   ⏭️  Rebalanceo saltado: ya en progreso")
        
        else:
            print(f"   ❌ Error: {result.get('message', 'Error desconocido')}")
            return False
        
        # 3. Verificar estado después del rebalanceo
        print(f"\n📊 Verificando estado después del rebalanceo...")
        status_after = await auto_rebalancer.get_rebalance_status()
        
        assets_after = status_after.get('assets_needing_rebalance', 0)
        improvement = assets_needing - assets_after
        
        print(f"   - Activos operativos mejorados: {improvement}")
        print(f"   - Activos restantes: {assets_after}")
        
        if improvement > 0:
            print(f"   ✅ Éxito: {improvement} activos activados")
        elif assets_after == 0:
            print(f"   ✅ Éxito: Todos los activos están operativos")
        else:
            print(f"   ⚠️  Aún faltan {assets_after} activos por rebalancear")
        
        # 4. Enviar notificación por Telegram
        try:
            total_spent = sum(r.get('usdt_spent', 0) for r in rebalance_results if r.get('status') == 'success')
            mensaje = f"🔄 Rebalanceo Inmediato Ejecutado\n\n"
            mensaje += f"✅ Activos activados: {improvement}\n"
            mensaje += f"📊 Activos restantes: {assets_after}\n"
            mensaje += f"💰 USDT invertido: ${total_spent:.2f}\n"
            mensaje += f"⏰ Ejecutado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await send_telegram_alert(mensaje)
            print(f"\n📱 Notificación enviada por Telegram")
            
        except Exception as e:
            logger.error(f"Error enviando notificación Telegram: {e}")
            print(f"   ⚠️  Error enviando notificación: {e}")
        
        # 5. Guardar reporte
        report = {
            "timestamp": datetime.now().isoformat(),
            "status_before": status,
            "rebalance_result": result,
            "status_after": status_after,
            "improvement": improvement,
            "assets_remaining": assets_after,
            "total_usdt_spent": total_spent if successful > 0 else 0
        }
        
        report_filename = f"rebalanceo_inmediato_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Reporte guardado en: {report_filename}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error ejecutando rebalanceo inmediato: {e}")
        print(f"❌ Error: {e}")
        
        # Enviar notificación de error
        try:
            error_msg = f"❌ Error en Rebalanceo Inmediato\n\n"
            error_msg += f"Error: {str(e)}\n"
            error_msg += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await send_telegram_alert(error_msg)
        except:
            pass
        
        return False


async def main():
    """Función principal"""
    
    print("🚀 Iniciando rebalanceo inmediato")
    print("=" * 60)
    
    # Ejecutar rebalanceo
    success = await ejecutar_rebalanceo_inmediato()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Rebalanceo completado exitosamente")
    else:
        print("❌ Rebalanceo falló")
    
    return success


if __name__ == "__main__":
    # Ejecutar el script
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 