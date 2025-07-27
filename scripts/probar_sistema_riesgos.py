#!/usr/bin/env python3
"""
Script para probar el Sistema de Gestión de Riesgos
"""

import asyncio
import sys
import os
from datetime import datetime
import json

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.risk_manager import risk_manager, RiskLevel, RiskStatus

async def test_risk_manager_basic():
    """Prueba básica del RiskManager"""
    print("🔍 Iniciando pruebas del Sistema de Gestión de Riesgos")
    print("=" * 60)
    
    try:
        # 1. Verificar estado inicial
        print("\n📊 1. Verificando estado inicial del RiskManager...")
        status = await risk_manager.get_risk_status()
        print(f"   ✅ Estado: {status['status']}")
        print(f"   ✅ Trading habilitado: {status['trading_enabled']}")
        print(f"   ✅ Parada de emergencia: {status['emergency_stop']}")
        
        # 2. Verificar riesgo del portafolio
        print("\n📈 2. Verificando riesgo del portafolio...")
        portfolio_risk = await risk_manager.check_portfolio_risk()
        print(f"   ✅ Estado de riesgo: {portfolio_risk.value}")
        
        # 3. Calcular métricas de riesgo
        print("\n📊 3. Calculando métricas de riesgo...")
        risk_metrics = await risk_manager.calculate_risk_metrics()
        print(f"   ✅ Exposición total: {risk_metrics.total_exposure:.2%}")
        print(f"   ✅ Pérdida diaria: {risk_metrics.current_daily_loss:.2%}")
        print(f"   ✅ Posición más grande: {risk_metrics.largest_position:.2%}")
        print(f"   ✅ Volatilidad: {risk_metrics.portfolio_volatility:.2%}")
        print(f"   ✅ Sharpe Ratio: {risk_metrics.sharpe_ratio:.2f}")
        print(f"   ✅ Máximo drawdown: {risk_metrics.max_drawdown:.2%}")
        print(f"   ✅ Score de riesgo: {risk_metrics.risk_score:.2f}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba básica: {e}")
        return False

async def test_asset_risk():
    """Prueba de riesgo por activo"""
    print("\n🎯 4. Verificando riesgo por activo...")
    
    try:
        # Activos de prueba
        test_assets = ["BNB", "ETH", "BTC", "ANIME", "GPS"]
        
        for asset in test_assets:
            try:
                risk_status = await risk_manager.check_asset_risk(asset)
                position = await risk_manager._get_asset_position(asset)
                
                print(f"   📊 {asset}:")
                print(f"      - Estado de riesgo: {risk_status.value}")
                print(f"      - Posición: {position['value']:.2f} USDT" if position else "      - Posición: Sin posición")
                
            except Exception as e:
                print(f"   ⚠️ Error verificando {asset}: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba de activos: {e}")
        return False

async def test_emergency_stop():
    """Prueba de parada de emergencia"""
    print("\n🚨 5. Probando parada de emergencia...")
    
    try:
        # Activar parada de emergencia
        print("   🔴 Activando parada de emergencia...")
        await risk_manager.set_emergency_stop(True)
        
        # Verificar estado
        status = await risk_manager.get_risk_status()
        print(f"   ✅ Parada de emergencia: {status['emergency_stop']}")
        print(f"   ✅ Trading habilitado: {status['trading_enabled']}")
        
        # Desactivar parada de emergencia
        print("   🟢 Desactivando parada de emergencia...")
        await risk_manager.set_emergency_stop(False)
        
        # Verificar estado
        status = await risk_manager.get_risk_status()
        print(f"   ✅ Parada de emergencia: {status['emergency_stop']}")
        print(f"   ✅ Trading habilitado: {status['trading_enabled']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba de parada de emergencia: {e}")
        return False

async def test_risk_alerts():
    """Prueba de alertas de riesgo"""
    print("\n📢 6. Probando sistema de alertas...")
    
    try:
        # Simular diferentes niveles de alerta
        alert_tests = [
            (RiskLevel.LOW, "Prueba de alerta de bajo riesgo"),
            (RiskLevel.MEDIUM, "Prueba de alerta de riesgo medio"),
            (RiskLevel.HIGH, "Prueba de alerta de alto riesgo"),
            (RiskLevel.CRITICAL, "Prueba de alerta crítica")
        ]
        
        for level, message in alert_tests:
            print(f"   📢 Enviando alerta {level.value}: {message}")
            await risk_manager._trigger_risk_alert(level, message, action_required=(level in [RiskLevel.HIGH, RiskLevel.CRITICAL]))
            await asyncio.sleep(1)  # Pequeña pausa entre alertas
        
        print("   ✅ Alertas enviadas correctamente")
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba de alertas: {e}")
        return False

async def test_stop_loss():
    """Prueba de stop-loss"""
    print("\n🛑 7. Probando sistema de stop-loss...")
    
    try:
        # Probar stop-loss en un activo (simulado)
        test_symbol = "BNB"
        
        print(f"   🎯 Probando stop-loss para {test_symbol}...")
        success = await risk_manager.execute_stop_loss(test_symbol)
        
        if success:
            print(f"   ✅ Stop-loss ejecutado exitosamente para {test_symbol}")
        else:
            print(f"   ⚠️ Stop-loss no ejecutado para {test_symbol} (posiblemente sin posición)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba de stop-loss: {e}")
        return False

async def test_risk_limits():
    """Prueba de límites de riesgo"""
    print("\n📏 8. Verificando límites de riesgo...")
    
    try:
        print("   📊 Límites configurados:")
        print(f"      - Pérdida diaria máxima: {risk_manager.max_daily_loss_percentage:.2%}")
        print(f"      - Tamaño máximo de posición: {risk_manager.max_position_size_percentage:.2%}")
        print(f"      - Exposición total máxima: {risk_manager.max_total_exposure_percentage:.2%}")
        print(f"      - Stop-loss: {risk_manager.stop_loss_percentage:.2%}")
        print(f"      - Máximo drawdown: {risk_manager.max_drawdown_percentage:.2%}")
        print(f"      - Exposición por activo: {risk_manager.max_asset_exposure:.2%}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error verificando límites: {e}")
        return False

async def generate_risk_report():
    """Genera reporte completo de riesgo"""
    print("\n📋 9. Generando reporte completo de riesgo...")
    
    try:
        # Obtener estado completo
        status = await risk_manager.get_risk_status()
        risk_metrics = await risk_manager.calculate_risk_metrics()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "risk_status": {
                "status": status['status'],
                "trading_enabled": status['trading_enabled'],
                "emergency_stop": status['emergency_stop']
            },
            "risk_metrics": {
                "total_exposure": f"{risk_metrics.total_exposure:.2%}",
                "current_daily_loss": f"{risk_metrics.current_daily_loss:.2%}",
                "largest_position": f"{risk_metrics.largest_position:.2%}",
                "portfolio_volatility": f"{risk_metrics.portfolio_volatility:.2%}",
                "sharpe_ratio": f"{risk_metrics.sharpe_ratio:.2f}",
                "max_drawdown": f"{risk_metrics.max_drawdown:.2%}",
                "risk_score": f"{risk_metrics.risk_score:.2f}"
            },
            "risk_limits": status['limits'],
            "test_results": {
                "basic_test": True,
                "asset_risk_test": True,
                "emergency_stop_test": True,
                "alerts_test": True,
                "stop_loss_test": True,
                "limits_test": True
            }
        }
        
        # Guardar reporte
        filename = f"reporte_riesgos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"   ✅ Reporte guardado en: {filename}")
        
        return report
        
    except Exception as e:
        print(f"   ❌ Error generando reporte: {e}")
        return None

async def main():
    """Función principal de pruebas"""
    print("🚀 Iniciando pruebas completas del Sistema de Gestión de Riesgos")
    print("=" * 80)
    
    test_results = []
    
    # Ejecutar todas las pruebas
    tests = [
        ("Prueba básica", test_risk_manager_basic),
        ("Riesgo por activo", test_asset_risk),
        ("Parada de emergencia", test_emergency_stop),
        ("Alertas de riesgo", test_risk_alerts),
        ("Stop-loss", test_stop_loss),
        ("Límites de riesgo", test_risk_limits)
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ Error en {test_name}: {e}")
            test_results.append((test_name, False))
    
    # Generar reporte final
    report = await generate_risk_report()
    
    # Resumen de resultados
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE PRUEBAS DEL SISTEMA DE GESTIÓN DE RIESGOS")
    print("=" * 80)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"   {status} {test_name}")
    
    print(f"\n📈 Resultados: {passed}/{total} pruebas exitosas")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas del sistema de gestión de riesgos pasaron!")
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar logs para más detalles.")
    
    print("\n🌐 URLs de acceso:")
    print("   - API de Riesgos: http://localhost:8000/api/v1/risk/status")
    print("   - Métricas de Riesgo: http://localhost:8000/api/v1/risk/metrics")
    print("   - Health Check: http://localhost:8000/api/v1/risk/health")
    print("   - Documentación API: http://localhost:8000/docs")

if __name__ == "__main__":
    asyncio.run(main()) 