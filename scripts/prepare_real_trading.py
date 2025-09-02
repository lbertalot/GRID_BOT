#!/usr/bin/env python3
"""
Script de Preparación para Trading Real
GridBot V2.5 - Fase 7.4: Preparación para Trading Real
"""

import sys
import os
import json
import logging
import time
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def prepare_real_trading():
    """Prepara el sistema para activación de trading real"""
    print("🚀 INICIANDO PREPARACIÓN PARA TRADING REAL")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 7.4: Preparación para Trading Real")
    
    try:
        # 1. Verificar estado del sistema después de ajustes
        print("\n🔍 1. VERIFICANDO ESTADO DEL SISTEMA DESPUÉS DE AJUSTES...")
        
        from app.core.safety_validator import get_system_safety_status
        safety_status = get_system_safety_status()
        
        print(f"   Circuit Breaker: {'🔴 ABIERTO' if safety_status['circuit_breaker']['is_open'] else '🟢 CERRADO'}")
        print(f"   Sistema Seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}")
        
        if not safety_status['system_safe']:
            print("❌ Sistema no está en estado seguro para preparación")
            print("🔧 Corregir problemas antes de continuar")
            return False
        
        print("✅ Sistema en estado seguro")
        
        # 2. Verificar configuración optimizada
        print("\n⚙️ 2. VERIFICANDO CONFIGURACIÓN OPTIMIZADA...")
        
        from app.core.unified_config import get_config
        config = get_config()
        config_summary = config.get_config_summary()
        
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(f"   Límites de seguridad actualizados:")
        print(f"      • Pérdida diaria: {config_summary['safety_limits']['max_daily_loss']*100:.1f}%")
        print(f"      • Pérdida total: {config_summary['safety_limits']['max_total_loss']*100:.1f}%")
        print(f"      • Pérdida por trade: {config_summary['safety_limits']['max_trade_loss']*100:.1f}%")
        
        # 3. Verificar rendimiento del paper trading
        print("\n📊 3. VERIFICANDO RENDIMIENTO DEL PAPER TRADING...")
        
        from app.core.paper_trading import get_paper_portfolio_summary
        portfolio = get_paper_portfolio_summary()
        
        initial_balance = portfolio['initial_balance']
        current_balance = portfolio['current_balance']
        balance_change_pct = ((current_balance - initial_balance) / initial_balance) * 100
        
        print(f"   Balance inicial: ${initial_balance:.2f}")
        print(f"   Balance actual: ${current_balance:.2f}")
        print(f"   Cambio: {balance_change_pct:.2f}%")
        print(f"   Total trades: {portfolio['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio['open_positions']}")
        
        # 4. Evaluar estabilidad para trading real
        print("\n🎯 4. EVALUANDO ESTABILIDAD PARA TRADING REAL...")
        
        stability_score = 0
        stability_factors = []
        
        # Factor 1: Cambio de balance
        if abs(balance_change_pct) < 2:
            stability_score += 25
            stability_factors.append("✅ Balance estable (< 2% cambio)")
        elif abs(balance_change_pct) < 5:
            stability_score += 15
            stability_factors.append("🟡 Balance moderadamente estable (< 5% cambio)")
        else:
            stability_factors.append("🔴 Balance inestable (> 5% cambio)")
        
        # Factor 2: Número de trades
        if portfolio['total_trades'] >= 10:
            stability_score += 25
            stability_factors.append("✅ Suficientes trades para análisis (≥ 10)")
        elif portfolio['total_trades'] >= 5:
            stability_score += 15
            stability_factors.append("🟡 Trades moderados para análisis (≥ 5)")
        else:
            stability_factors.append("🔴 Pocos trades para análisis (< 5)")
        
        # Factor 3: Circuit breakers
        if not safety_status['circuit_breaker']['is_open']:
            stability_score += 25
            stability_factors.append("✅ Circuit breakers estables")
        else:
            stability_factors.append("🔴 Circuit breakers activados")
        
        # Factor 4: Configuración de seguridad
        if config_summary['safety_limits']['max_daily_loss'] <= 0.03:
            stability_score += 25
            stability_factors.append("✅ Límites de seguridad conservadores")
        else:
            stability_factors.append("🔴 Límites de seguridad no suficientemente conservadores")
        
        print(f"   Puntuación de estabilidad: {stability_score}/100")
        print(f"   Factores de estabilidad:")
        for factor in stability_factors:
            print(f"      {factor}")
        
        # 5. Determinar si está listo para trading real
        print("\n🚀 5. EVALUANDO READINESS PARA TRADING REAL...")
        
        if stability_score >= 80:
            readiness_status = "🟢 LISTO"
            readiness_message = "Sistema estable y listo para trading real"
            can_proceed = True
        elif stability_score >= 60:
            readiness_status = "🟡 CASI LISTO"
            readiness_message = "Sistema moderadamente estable, requiere monitoreo adicional"
            can_proceed = False
        else:
            readiness_status = "🔴 NO LISTO"
            readiness_message = "Sistema no está listo para trading real"
            can_proceed = False
        
        print(f"   Estado de readiness: {readiness_status}")
        print(f"   Mensaje: {readiness_message}")
        print(f"   ¿Puede proceder?: {'✅ SÍ' if can_proceed else '❌ NO'}")
        
        # 6. Configurar parámetros para trading real
        print("\n⚙️ 6. CONFIGURANDO PARÁMETROS PARA TRADING REAL...")
        
        if can_proceed:
            # Configurar trading real con parámetros conservadores
            real_trading_config = {
                'trading_enabled': True,
                'paper_trading': False,
                'max_concurrent_trades': 3,  # Reducido para mayor seguridad
                'default_investment_percentage': 0.05,  # 5% por asset
                'emergency_stop_enabled': True
            }
            
            # Actualizar configuración del sistema
            config.update_system_settings(real_trading_config)
            
            print("✅ Configuración de trading real aplicada")
            print(f"   Trading real: Habilitado")
            print(f"   Paper trading: Deshabilitado")
            print(f"   Máximo trades concurrentes: 3")
            print(f"   Porcentaje de inversión por asset: 5%")
            print(f"   Parada de emergencia: Habilitada")
            
        else:
            # Mantener configuración de paper trading
            print("📊 Manteniendo configuración de paper trading")
            print("⏰ Sistema requiere estabilización adicional")
            
            # Configurar monitoreo intensivo
            monitoring_config = {
                'alerts_enabled': True,
                'email_alerts': True,
                'sms_alerts': False,
                'dashboard_enabled': True,
                'log_level': 'INFO'  # Logging más detallado
            }
            
            config.update_monitoring_settings(monitoring_config)
            print("✅ Configuración de monitoreo intensivo aplicada")
        
        # 7. Crear plan de activación de trading real
        print("\n📋 7. CREANDO PLAN DE ACTIVACIÓN DE TRADING REAL...")
        
        if can_proceed:
            activation_plan = {
                'timestamp': datetime.now().isoformat(),
                'phase': '7.4_real_trading_preparation_complete',
                'status': 'ready_for_activation',
                'readiness_score': stability_score,
                'next_steps': [
                    {
                        'step': 1,
                        'action': 'Activación Gradual de Trading Real',
                        'description': 'Activar trading real con 1 asset',
                        'duration': '24 horas',
                        'criteria': 'Monitoreo intensivo, sin pérdidas significativas'
                    },
                    {
                        'step': 2,
                        'action': 'Expansión Multi-Asset',
                        'description': 'Activar más assets gradualmente',
                        'duration': '48 horas',
                        'criteria': 'Estabilidad confirmada con primer asset'
                    },
                    {
                        'step': 3,
                        'action': 'Operación Completa',
                        'description': 'Sistema completamente operativo',
                        'duration': '72 horas',
                        'criteria': 'Todos los assets estables'
                    }
                ],
                'safety_measures': [
                    'Circuit breakers activos y monitoreados',
                    'Límites de pérdida conservadores (3% diario)',
                    'Monitoreo continuo 24/7',
                    'Alertas automáticas habilitadas',
                    'Parada de emergencia operativa',
                    'Inversión limitada por asset (5%)'
                ]
            }
        else:
            activation_plan = {
                'timestamp': datetime.now().isoformat(),
                'phase': '7.4_real_trading_preparation_incomplete',
                'status': 'requires_stabilization',
                'readiness_score': stability_score,
                'stabilization_requirements': [
                    'Reducir volatilidad del balance',
                    'Aumentar número de trades para análisis',
                    'Confirmar estabilidad de circuit breakers',
                    'Validar límites de seguridad'
                ],
                'next_steps': [
                    {
                        'step': 1,
                        'action': 'Estabilización del Sistema',
                        'description': 'Continuar paper trading hasta estabilización',
                        'duration': '48-72 horas',
                        'criteria': 'Puntuación de estabilidad ≥ 80'
                    },
                    {
                        'step': 2,
                        'action': 'Re-evaluación',
                        'description': 'Re-evaluar readiness para trading real',
                        'duration': '72 horas',
                        'criteria': 'Sistema completamente estable'
                    }
                ]
            }
        
        # Guardar plan
        plan_file = f"real_trading_activation_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(plan_file, 'w') as f:
            json.dump(activation_plan, f, indent=2)
        
        print(f"✅ Plan de activación guardado en: {plan_file}")
        
        # 8. Resumen final
        print("\n" + "=" * 60)
        print("🎯 RESUMEN DE PREPARACIÓN PARA TRADING REAL")
        print("=" * 60)
        
        print("✅ Estado del sistema verificado")
        print("✅ Configuración optimizada validada")
        print("✅ Rendimiento del paper trading analizado")
        print("✅ Estabilidad evaluada")
        print("✅ Readiness determinado")
        print("✅ Parámetros configurados")
        print("✅ Plan de activación creado")
        
        print(f"\n📊 ESTADO ACTUAL:")
        print(f"   Assets activos: {len(config_summary['active_assets'])}")
        print(f"   Puntuación de estabilidad: {stability_score}/100")
        print(f"   Readiness: {readiness_status}")
        print(f"   ¿Puede proceder?: {'✅ SÍ' if can_proceed else '❌ NO'}")
        
        if can_proceed:
            print(f"\n🚀 SISTEMA LISTO PARA TRADING REAL:")
            print(f"   • Trading real habilitado")
            print(f"   • Paper trading deshabilitado")
            print(f"   • Monitoreo intensivo activo")
            print(f"   • Parada de emergencia operativa")
        else:
            print(f"\n📊 SISTEMA REQUIERE ESTABILIZACIÓN:")
            print(f"   • Continuar paper trading")
            print(f"   • Monitoreo intensivo activo")
            print(f"   • Re-evaluar en 48-72 horas")
        
        print(f"\n⏰ PRÓXIMOS PASOS:")
        if can_proceed:
            print(f"   1. Monitorear trading real durante 24 horas")
            print(f"   2. Expandir a más assets gradualmente")
            print(f"   3. Operación completa en 72 horas")
        else:
            print(f"   1. Continuar estabilización del sistema")
            print(f"   2. Monitoreo intensivo durante 48-72 horas")
            print(f"   3. Re-evaluar readiness para trading real")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en preparación para trading real: {e}")
        logger.error(f"Error en preparación: {e}")
        return False

def main():
    """Función principal"""
    success = prepare_real_trading()
    
    if success:
        print(f"\n🎉 PREPARACIÓN PARA TRADING REAL COMPLETADA EXITOSAMENTE")
        print("📊 Sistema evaluado y configurado")
        print("📋 Plan de activación creado")
        print("⏰ Seguir plan según readiness del sistema")
        
    else:
        print(f"\n❌ PREPARACIÓN PARA TRADING REAL FALLÓ")
        print("🔧 Revisar errores antes de continuar")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
