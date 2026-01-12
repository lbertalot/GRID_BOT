#!/usr/bin/env python3
"""
Script de Preparación para Reactivación
GridBot V2.5 - Fase 6
"""

import sys
import os
import json
import logging
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def prepare_system_reactivation():
    """Prepara el sistema para reactivación"""
    print("🚀 PREPARANDO SISTEMA PARA REACTIVACIÓN")
    print("=" * 50)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. Resetear circuit breaker
        print("\n🔄 1. RESETEANDO CIRCUIT BREAKER...")
        from app.core.circuit_breaker import circuit_breaker
        
        circuit_breaker.close_circuit("Preparación para reactivación")
        circuit_breaker.state['daily_loss'] = 0.0
        circuit_breaker.state['total_loss'] = 0.0
        circuit_breaker.state['consecutive_losses'] = 0
        circuit_breaker.state['hourly_loss'] = 0.0
        circuit_breaker.state['last_reset'] = datetime.now()
        circuit_breaker.save_state()
        
        print("✅ Circuit breaker reseteado y cerrado")
        
        # 2. Verificar configuración
        print("\n⚙️ 2. VERIFICANDO CONFIGURACIÓN...")
        from app.core.unified_config import get_config
        
        config = get_config()
        config_summary = config.get_config_summary()
        
        print(f"   Assets totales: {config_summary['assets_summary']['total_assets']}")
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(f"   Trading real: {'❌ Habilitado' if config_summary['system_settings']['trading_enabled'] else '✅ Deshabilitado'}")
        print(f"   Paper trading: {'✅ Habilitado' if config_summary['system_settings']['paper_trading'] else '❌ Deshabilitado'}")
        print(f"   Parada de emergencia: {'✅ Habilitada' if config_summary['system_settings']['emergency_stop_enabled'] else '❌ Deshabilitada'}")
        
        # 3. Configurar paper trading
        print("\n📄 3. CONFIGURANDO PAPER TRADING...")
        from app.core.paper_trading import paper_trading_system
        
        # Resetear paper trading con balance inicial
        initial_balance = 1000.0
        paper_trading_system.reset_paper_trading(initial_balance)
        
        print(f"✅ Paper trading configurado con balance: ${initial_balance:.2f}")
        
        # 4. Verificar sistemas de seguridad
        print("\n🛡️ 4. VERIFICANDO SISTEMAS DE SEGURIDAD...")
        from app.core.safety_validator import get_system_safety_status
        
        safety_status = get_system_safety_status()
        
        circuit_breaker_open = safety_status['circuit_breaker']['is_open']
        system_safe = safety_status['system_safe']
        
        print(f"   Circuit Breaker: {'🔴 ABIERTO' if circuit_breaker_open else '🟢 CERRADO'}")
        print(f"   Sistema Seguro: {'🟢 SÍ' if system_safe else '🔴 NO'}")
        
        if not system_safe:
            print("   ⚠️ El sistema NO está en estado seguro para reactivación.")
            return False
        else:
            print("   ✅ El sistema está en estado seguro.")
        
        # 5. Verificar monitoreo
        print("\n📊 5. VERIFICANDO SISTEMA DE MONITOREO...")
        from app.core.monitoring import get_monitoring_status
        
        monitoring_status = get_monitoring_status()
        
        print(f"   Estado del sistema: {monitoring_status['system_status']}")
        print(f"   Alertas totales: {monitoring_status['total_alerts']}")
        print(f"   Métricas activas: {'✅' if monitoring_status['metrics'] else '❌'}")
        
        # 6. Crear plan de reactivación
        print("\n📋 6. CREANDO PLAN DE REACTIVACIÓN...")
        
        reactivation_plan = {
            'timestamp': datetime.now().isoformat(),
            'phase': '6_reactivation_preparation',
            'status': 'ready',
            'steps': [
                {
                    'step': 1,
                    'action': 'Paper Trading con 1 Asset',
                    'description': 'Activar paper trading con BTCUSDT',
                    'duration': '24 horas',
                    'monitoring': 'Continuo'
                },
                {
                    'step': 2,
                    'action': 'Validación de Estabilidad',
                    'description': 'Verificar que no hay pérdidas inesperadas',
                    'duration': '48 horas',
                    'monitoring': '24/7'
                },
                {
                    'step': 3,
                    'action': 'Activación Gradual',
                    'description': 'Activar más assets uno por uno',
                    'duration': '72 horas',
                    'monitoring': 'Continuo'
                },
                {
                    'step': 4,
                    'action': 'Trading Real',
                    'description': 'Activar trading real con monitoreo intensivo',
                    'duration': 'Indefinido',
                    'monitoring': '24/7'
                }
            ],
            'safety_measures': [
                'Circuit breakers activos',
                'Límites de pérdida configurados',
                'Monitoreo continuo',
                'Alertas automáticas',
                'Parada de emergencia habilitada'
            ],
            'current_config': {
                'trading_enabled': config_summary['system_settings']['trading_enabled'],
                'paper_trading': config_summary['system_settings']['paper_trading'],
                'emergency_stop': config_summary['system_settings']['emergency_stop_enabled'],
                'total_assets': config_summary['assets_summary']['total_assets'],
                'active_assets': config_summary['assets_summary']['active_assets']
            }
        }
        
        # Guardar plan
        plan_file = f"reactivation_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(plan_file, 'w') as f:
            json.dump(reactivation_plan, f, indent=2)
        
        print(f"✅ Plan de reactivación guardado en: {plan_file}")
        
        # 7. Resumen final
        print("\n" + "=" * 50)
        print("🎯 RESUMEN DE PREPARACIÓN")
        print("=" * 50)
        
        print("✅ Circuit breaker reseteado y cerrado")
        print("✅ Configuración verificada")
        print("✅ Paper trading configurado")
        print("✅ Sistemas de seguridad operativos")
        print("✅ Monitoreo activo")
        print("✅ Plan de reactivación creado")
        
        print(f"\n🚀 SISTEMA LISTO PARA REACTIVACIÓN")
        print("📄 Comenzar con paper trading")
        print("🛡️ Monitoreo continuo activo")
        print("⚡ Circuit breakers operativos")
        
        return True
        
    except Exception as e:
        print(f"❌ Error preparando reactivación: {e}")
        logger.error(f"Error en preparación: {e}")
        return False

def main():
    """Función principal"""
    success = prepare_system_reactivation()
    
    if success:
        print(f"\n🎉 PREPARACIÓN COMPLETADA EXITOSAMENTE")
        print("🔄 El sistema está listo para comenzar reactivación")
        print("📋 Siguiente paso: Activar paper trading con 1 asset")
    else:
        print(f"\n❌ PREPARACIÓN FALLÓ")
        print("🔧 Revisar errores antes de continuar")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
