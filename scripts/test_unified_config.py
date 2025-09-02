#!/usr/bin/env python3
"""
Script de Prueba del Sistema de Configuración Unificado
GridBot V2.5
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

def test_config_loading():
    """Prueba la carga de configuración"""
    print("\n📁 PROBANDO CARGA DE CONFIGURACIÓN")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        print("✅ Configuración cargada exitosamente")
        
        # Mostrar resumen
        summary = config.get_config_summary()
        print(f"   Total assets: {summary['assets_summary']['total_assets']}")
        print(f"   Assets activos: {summary['assets_summary']['active_assets']}")
        print(f"   Trading habilitado: {summary['system_settings']['trading_enabled']}")
        print(f"   Paper trading: {summary['system_settings']['paper_trading']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")
        return False

def test_asset_management():
    """Prueba la gestión de assets"""
    print("\n💰 PROBANDO GESTIÓN DE ASSETS")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        
        # Obtener assets actuales
        assets = config.get_all_assets()
        print(f"✅ Assets actuales: {len(assets)}")
        
        # Probar obtener asset específico
        btc_config = config.get_asset_config("BTCUSDT")
        if btc_config:
            print(f"✅ Configuración BTCUSDT obtenida")
            print(f"   Activo: {btc_config.get('is_active', False)}")
            print(f"   Precio min: ${btc_config.get('min_price', 0)}")
            print(f"   Precio max: ${btc_config.get('max_price', 0)}")
        
        # Probar activar/desactivar asset
        if btc_config:
            original_state = btc_config.get('is_active', False)
            
            # Cambiar estado
            btc_config['is_active'] = not original_state
            config.update_asset_config("BTCUSDT", btc_config)
            print(f"✅ Estado de BTCUSDT cambiado a: {btc_config['is_active']}")
            
            # Restaurar estado original
            btc_config['is_active'] = original_state
            config.update_asset_config("BTCUSDT", btc_config)
            print(f"✅ Estado de BTCUSDT restaurado a: {original_state}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en gestión de assets: {e}")
        return False

def test_safety_limits():
    """Prueba los límites de seguridad"""
    print("\n🛡️ PROBANDO LÍMITES DE SEGURIDAD")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        
        # Obtener límites actuales
        limits = config.get_safety_limits()
        print("✅ Límites de seguridad obtenidos:")
        print(f"   Pérdida diaria máxima: {limits.get('max_daily_loss', 0) * 100:.1f}%")
        print(f"   Pérdida total máxima: {limits.get('max_total_loss', 0) * 100:.1f}%")
        print(f"   Pérdida por trade máxima: {limits.get('max_trade_loss', 0) * 100:.1f}%")
        print(f"   Pérdidas consecutivas máximas: {limits.get('max_consecutive_losses', 0)}")
        print(f"   Balance mínimo: ${limits.get('min_balance', 0):.2f}")
        
        # Probar actualizar límites
        new_limits = {
            'max_daily_loss': 0.06,  # 6%
            'max_total_loss': 0.12,  # 12%
            'max_trade_loss': 0.025,  # 2.5%
            'max_consecutive_losses': 4,
            'max_hourly_loss': 0.04,  # 4%
            'min_balance': 60.0,
            'min_notional_value': 15.0
        }
        
        config.update_safety_limits(new_limits)
        print("✅ Límites de seguridad actualizados")
        
        # Verificar cambios
        updated_limits = config.get_safety_limits()
        print(f"   Nueva pérdida diaria máxima: {updated_limits.get('max_daily_loss', 0) * 100:.1f}%")
        print(f"   Nuevo balance mínimo: ${updated_limits.get('min_balance', 0):.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en límites de seguridad: {e}")
        return False

def test_monitoring_settings():
    """Prueba la configuración de monitoreo"""
    print("\n📊 PROBANDO CONFIGURACIÓN DE MONITOREO")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        
        # Obtener configuración actual
        monitoring = config.get_monitoring_settings()
        print("✅ Configuración de monitoreo obtenida:")
        print(f"   Alertas habilitadas: {monitoring.get('alerts_enabled', False)}")
        print(f"   Alertas por email: {monitoring.get('email_alerts', False)}")
        print(f"   Alertas por SMS: {monitoring.get('sms_alerts', False)}")
        print(f"   Dashboard habilitado: {monitoring.get('dashboard_enabled', False)}")
        print(f"   Nivel de log: {monitoring.get('log_level', 'INFO')}")
        
        # Probar actualizar configuración
        new_monitoring = {
            'alerts_enabled': True,
            'email_alerts': True,
            'sms_alerts': False,
            'dashboard_enabled': True,
            'log_level': 'WARNING'
        }
        
        config.update_monitoring_settings(new_monitoring)
        print("✅ Configuración de monitoreo actualizada")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en configuración de monitoreo: {e}")
        return False

def test_system_settings():
    """Prueba la configuración del sistema"""
    print("\n⚙️ PROBANDO CONFIGURACIÓN DEL SISTEMA")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        
        # Obtener configuración actual
        system = config.get_system_settings()
        print("✅ Configuración del sistema obtenida:")
        print(f"   Trading habilitado: {system.get('trading_enabled', False)}")
        print(f"   Paper trading: {system.get('paper_trading', False)}")
        print(f"   Trades concurrentes máximos: {system.get('max_concurrent_trades', 0)}")
        print(f"   Porcentaje de inversión por defecto: {system.get('default_investment_percentage', 0) * 100:.1f}%")
        print(f"   Parada de emergencia habilitada: {system.get('emergency_stop_enabled', False)}")
        
        # Probar habilitar/deshabilitar trading
        original_trading = system.get('trading_enabled', False)
        
        if not original_trading:
            config.enable_trading()
            print("✅ Trading habilitado")
            
            config.disable_trading()
            print("✅ Trading deshabilitado")
        else:
            config.disable_trading()
            print("✅ Trading deshabilitado")
            
            config.enable_trading()
            print("✅ Trading habilitado")
        
        # Probar paper trading
        original_paper = system.get('paper_trading', False)
        
        if not original_paper:
            config.enable_paper_trading()
            print("✅ Paper trading habilitado")
            
            config.disable_paper_trading()
            print("✅ Paper trading deshabilitado")
        else:
            config.disable_paper_trading()
            print("✅ Paper trading deshabilitado")
            
            config.enable_paper_trading()
            print("✅ Paper trading habilitado")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en configuración del sistema: {e}")
        return False

def test_config_validation():
    """Prueba la validación de configuración"""
    print("\n🔍 PROBANDO VALIDACIÓN DE CONFIGURACIÓN")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        
        # Validar configuración actual
        is_valid, errors = config.validate_config()
        
        if is_valid:
            print("✅ Configuración válida")
        else:
            print(f"❌ Configuración inválida: {len(errors)} errores")
            for error in errors:
                print(f"   - {error}")
        
        return is_valid
        
    except Exception as e:
        print(f"❌ Error validando configuración: {e}")
        return False

def test_config_persistence():
    """Prueba la persistencia de configuración"""
    print("\n💾 PROBANDO PERSISTENCIA DE CONFIGURACIÓN")
    print("=" * 40)
    
    try:
        from app.core.unified_config import get_config
        
        config = get_config()
        
        # Crear backup de configuración actual
        original_summary = config.get_config_summary()
        
        # Modificar configuración
        config.update_system_settings({
            'trading_enabled': True,
            'paper_trading': False,
            'max_concurrent_trades': 10,
            'default_investment_percentage': 0.15,
            'emergency_stop_enabled': True
        })
        
        print("✅ Configuración modificada")
        
        # Recargar configuración
        config.load_config()
        
        # Verificar que los cambios se guardaron
        new_summary = config.get_config_summary()
        
        if new_summary['system_settings']['trading_enabled']:
            print("✅ Configuración persistida correctamente")
        else:
            print("❌ Configuración no se persistió correctamente")
            return False
        
        # Restaurar configuración original
        config.update_system_settings(original_summary['system_settings'])
        print("✅ Configuración original restaurada")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en persistencia de configuración: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("🧪 INICIANDO PRUEBAS DEL SISTEMA DE CONFIGURACIÓN UNIFICADO")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Ejecutar todas las pruebas
    tests = [
        ("Carga de Configuración", test_config_loading),
        ("Gestión de Assets", test_asset_management),
        ("Límites de Seguridad", test_safety_limits),
        ("Configuración de Monitoreo", test_monitoring_settings),
        ("Configuración del Sistema", test_system_settings),
        ("Validación de Configuración", test_config_validation),
        ("Persistencia de Configuración", test_config_persistence),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Error en prueba {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen de resultados
    print("\n" + "="*60)
    print("📊 RESUMEN DE PRUEBAS")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡TODAS LAS PRUEBAS PASARON! El sistema de configuración unificado está funcionando correctamente.")
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar los errores antes de continuar.")
    
    # Mostrar resumen final de configuración
    try:
        from app.core.unified_config import get_config
        config = get_config()
        summary = config.get_config_summary()
        
        print(f"\n📋 RESUMEN FINAL DE CONFIGURACIÓN:")
        print(f"   Assets totales: {summary['assets_summary']['total_assets']}")
        print(f"   Assets activos: {summary['assets_summary']['active_assets']}")
        print(f"   Trading: {'✅ Habilitado' if summary['system_settings']['trading_enabled'] else '❌ Deshabilitado'}")
        print(f"   Paper Trading: {'✅ Habilitado' if summary['system_settings']['paper_trading'] else '❌ Deshabilitado'}")
        print(f"   Parada de Emergencia: {'✅ Habilitada' if summary['system_settings']['emergency_stop_enabled'] else '❌ Deshabilitada'}")
        
    except Exception as e:
        print(f"❌ Error obteniendo resumen final: {e}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
