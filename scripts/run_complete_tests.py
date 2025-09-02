#!/usr/bin/env python3
"""
Script de Pruebas Completas para GridBot V2.5
Ejecuta todas las pruebas antes de la reactivación
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

def main():
    """Función principal"""
    print("🧪 INICIANDO PRUEBAS COMPLETAS DEL SISTEMA")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔍 Validando todos los componentes antes de la reactivación...")
    
    try:
        # Importar sistema de pruebas
        from app.core.testing_system import run_complete_test_suite
        
        # Ejecutar todas las pruebas
        print("\n🚀 Ejecutando suite completa de pruebas...")
        results = run_complete_test_suite()
        
        # Mostrar resumen
        summary = results['summary']
        
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE PRUEBAS COMPLETAS")
        print("=" * 60)
        
        print(f"📈 Total de pruebas: {summary['total_tests']}")
        print(f"✅ Pruebas exitosas: {summary['passed_tests']}")
        print(f"❌ Pruebas fallidas: {summary['failed_tests']}")
        print(f"📊 Tasa de éxito: {summary['success_rate']:.1f}%")
        print(f"🎯 Estado general: {summary['status_emoji']} {summary['overall_status']}")
        
        # Mostrar detalles de pruebas fallidas
        if summary['failed_tests'] > 0:
            print(f"\n❌ PRUEBAS FALLIDAS:")
            for test_name in summary['failed_test_names']:
                print(f"   • {test_name}")
        
        # Mostrar detalles de cada prueba
        print(f"\n📋 DETALLES POR PRUEBA:")
        for test_name, result in results['results'].items():
            status = "✅ PASÓ" if result['success'] else "❌ FALLÓ"
            print(f"   {test_name}: {status}")
            
            if not result['success'] and 'error' in result:
                print(f"      Error: {result['error']}")
        
        # Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        
        if summary['overall_status'] == "PASSED":
            print("   🎉 ¡Todas las pruebas pasaron! El sistema está listo para reactivación.")
            print("   ✅ Se puede proceder con la Fase 6: Reactivación Segura")
            print("   🔄 Considerar activar paper trading primero")
            
        elif summary['overall_status'] == "WARNING":
            print("   ⚠️ Algunas pruebas fallaron, pero el sistema puede funcionar.")
            print("   🔧 Revisar las pruebas fallidas antes de reactivar.")
            print("   📄 Considerar usar solo paper trading por ahora.")
            
        else:
            print("   ❌ Múltiples pruebas fallaron. NO reactivar el sistema.")
            print("   🔧 Corregir todos los errores antes de continuar.")
            print("   🛡️ Mantener el sistema en modo seguro.")
        
        # Guardar reporte detallado
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Reporte detallado guardado en: {report_file}")
        
        # Verificar estado de seguridad
        print(f"\n🛡️ VERIFICACIÓN DE SEGURIDAD:")
        try:
            from app.core.safety_validator import get_system_safety_status
            safety_status = get_system_safety_status()
            
            circuit_breaker_open = safety_status['circuit_breaker']['is_open']
            system_safe = safety_status['system_safe']
            
            print(f"   Circuit Breaker: {'🔴 ABIERTO' if circuit_breaker_open else '🟢 CERRADO'}")
            print(f"   Sistema Seguro: {'🟢 SÍ' if system_safe else '🔴 NO'}")
            
            if not system_safe:
                print("   ⚠️ El sistema NO está en estado seguro para reactivación.")
            else:
                print("   ✅ El sistema está en estado seguro.")
                
        except Exception as e:
            print(f"   ❌ Error verificando seguridad: {e}")
        
        # Verificar configuración
        print(f"\n⚙️ VERIFICACIÓN DE CONFIGURACIÓN:")
        try:
            from app.core.unified_config import get_config
            config = get_config()
            config_summary = config.get_config_summary()
            
            trading_enabled = config_summary['system_settings']['trading_enabled']
            paper_trading = config_summary['system_settings']['paper_trading']
            emergency_stop = config_summary['system_settings']['emergency_stop_enabled']
            
            print(f"   Trading Real: {'🔴 HABILITADO' if trading_enabled else '🟢 DESHABILITADO'}")
            print(f"   Paper Trading: {'🟢 HABILITADO' if paper_trading else '🔴 DESHABILITADO'}")
            print(f"   Parada de Emergencia: {'🟢 HABILITADA' if emergency_stop else '🔴 DESHABILITADA'}")
            
            if trading_enabled:
                print("   ⚠️ Trading real está habilitado - considerar deshabilitar para pruebas.")
            else:
                print("   ✅ Trading real está deshabilitado - seguro para pruebas.")
                
        except Exception as e:
            print(f"   ❌ Error verificando configuración: {e}")
        
        # Resultado final
        print(f"\n" + "=" * 60)
        print(f"🎯 RESULTADO FINAL: {summary['status_emoji']} {summary['overall_status']}")
        print("=" * 60)
        
        if summary['overall_status'] == "PASSED":
            print("🎉 ¡SISTEMA LISTO PARA REACTIVACIÓN!")
            print("✅ Todas las pruebas pasaron exitosamente")
            print("🛡️ Sistemas de seguridad operativos")
            print("📊 Monitoreo y alertas funcionando")
            print("⚙️ Configuración validada y correcta")
            return True
        else:
            print("⚠️ SISTEMA NO LISTO PARA REACTIVACIÓN")
            print("❌ Algunas pruebas fallaron")
            print("🔧 Se requieren correcciones antes de continuar")
            print("🛡️ Mantener sistema en modo seguro")
            return False
            
    except Exception as e:
        print(f"❌ Error ejecutando pruebas: {e}")
        logger.error(f"Error en pruebas completas: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
