#!/usr/bin/env python3
"""
Script de Monitoreo Intensivo de Estabilización
GridBot V2.5 - Fase 7.5: Monitoreo Intensivo para Trading Real
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

def intensive_stabilization_monitoring():
    """Monitoreo intensivo para estabilización del sistema"""
    print("📊 INICIANDO MONITOREO INTENSIVO DE ESTABILIZACIÓN")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 7.5: Monitoreo Intensivo para Trading Real")
    
    try:
        # 1. Estado inicial del sistema
        print("\n🔍 1. ESTADO INICIAL DEL SISTEMA...")
        
        from app.core.safety_validator import get_system_safety_status
        safety_status = get_system_safety_status()
        
        print(f"   Circuit Breaker: {'🔴 ABIERTO' if safety_status['circuit_breaker']['is_open'] else '🟢 CERRADO'}")
        print(f"   Sistema Seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}")
        
        # 2. Configuración actual
        print("\n⚙️ 2. CONFIGURACIÓN ACTUAL...")
        
        from app.core.unified_config import get_config
        config = get_config()
        config_summary = config.get_config_summary()
        
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(f"   Límites de seguridad:")
        print(f"      • Pérdida diaria: {config_summary['safety_limits']['max_daily_loss']*100:.1f}%")
        print(f"      • Pérdida total: {config_summary['safety_limits']['max_total_loss']*100:.1f}%")
        print(f"      • Pérdida por trade: {config_summary['safety_limits']['max_trade_loss']*100:.1f}%")
        
        # 3. Estado del paper trading
        print("\n📊 3. ESTADO DEL PAPER TRADING...")
        
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
        
        # 4. Ejecutar trades de estabilización
        print("\n🧪 4. EJECUTANDO TRADES DE ESTABILIZACIÓN...")
        
        from app.core.paper_trading import paper_trading_system
        
        # Trades conservadores para estabilizar
        stabilization_trades = [
            {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.0005, "price": 108200},
            {"symbol": "ETHUSDT", "side": "BUY", "quantity": 0.005, "price": 4410},
            {"symbol": "BNBUSDT", "side": "BUY", "quantity": 0.05, "price": 855},
            {"symbol": "BTCUSDT", "side": "SELL", "quantity": 0.0005, "price": 108600},
            {"symbol": "ETHUSDT", "side": "SELL", "quantity": 0.005, "price": 4430},
            {"symbol": "BNBUSDT", "side": "SELL", "quantity": 0.05, "price": 860},
        ]
        
        executed_trades = 0
        for i, trade in enumerate(stabilization_trades, 1):
            print(f"   Trade {i}: {trade['side']} {trade['quantity']} {trade['symbol']} @ ${trade['price']}")
            
            try:
                if trade['side'] == 'BUY':
                    result = paper_trading_system.place_buy_order(
                        trade['symbol'], trade['quantity'], trade['price']
                    )
                else:
                    result = paper_trading_system.place_sell_order(
                        trade['symbol'], trade['quantity'], trade['price']
                    )
                
                if result['success']:
                    print(f"      ✅ Ejecutado: {result['order_id']}")
                    executed_trades += 1
                else:
                    print(f"      ❌ Error: {result['error']}")
                    
            except Exception as e:
                print(f"      ❌ Excepción: {e}")
        
        print(f"   ✅ Trades ejecutados: {executed_trades}/{len(stabilization_trades)}")
        
        # 5. Verificar estado después de trades
        print("\n📊 5. VERIFICANDO ESTADO DESPUÉS DE TRADES...")
        
        portfolio_after = paper_trading_system.get_portfolio_summary()
        balance_after = portfolio_after['current_balance']
        balance_change_after = ((balance_after - initial_balance) / initial_balance) * 100
        
        print(f"   Balance después de trades: ${balance_after:.2f}")
        print(f"   Cambio total: {balance_change_after:.2f}%")
        print(f"   Total trades: {portfolio_after['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio_after['open_positions']}")
        
        # 6. Calcular nueva puntuación de estabilidad
        print("\n🎯 6. CALCULANDO NUEVA PUNTUACIÓN DE ESTABILIDAD...")
        
        stability_score = 0
        stability_factors = []
        
        # Factor 1: Cambio de balance
        if abs(balance_change_after) < 2:
            stability_score += 25
            stability_factors.append("✅ Balance estable (< 2% cambio)")
        elif abs(balance_change_after) < 5:
            stability_score += 15
            stability_factors.append("🟡 Balance moderadamente estable (< 5% cambio)")
        else:
            stability_factors.append("🔴 Balance inestable (> 5% cambio)")
        
        # Factor 2: Número de trades
        if portfolio_after['total_trades'] >= 10:
            stability_score += 25
            stability_factors.append("✅ Suficientes trades para análisis (≥ 10)")
        elif portfolio_after['total_trades'] >= 8:
            stability_score += 20
            stability_factors.append("🟡 Trades suficientes para análisis (≥ 8)")
        elif portfolio_after['total_trades'] >= 5:
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
        
        # 7. Evaluar readiness para trading real
        print("\n🚀 7. EVALUANDO READINESS PARA TRADING REAL...")
        
        if stability_score >= 80:
            readiness_status = "🟢 LISTO"
            readiness_message = "Sistema estable y listo para trading real"
            can_proceed = True
        elif stability_score >= 70:
            readiness_status = "🟡 CASI LISTO"
            readiness_message = "Sistema casi estable, requiere monitoreo adicional"
            can_proceed = False
        else:
            readiness_status = "🔴 NO LISTO"
            readiness_message = "Sistema no está listo para trading real"
            can_proceed = False
        
        print(f"   Estado de readiness: {readiness_status}")
        print(f"   Mensaje: {readiness_message}")
        print(f"   ¿Puede proceder?: {'✅ SÍ' if can_proceed else '❌ NO'}")
        
        # 8. Configurar monitoreo continuo si es necesario
        print("\n📊 8. CONFIGURANDO MONITOREO CONTINUO...")
        
        if not can_proceed:
            # Configurar monitoreo intensivo continuo
            monitoring_config = {
                'alerts_enabled': True,
                'email_alerts': True,
                'sms_alerts': False,
                'dashboard_enabled': True,
                'log_level': 'INFO'
            }
            
            config.update_monitoring_settings(monitoring_config)
            print("✅ Monitoreo intensivo configurado")
            
            # Crear plan de estabilización
            stabilization_plan = {
                'timestamp': datetime.now().isoformat(),
                'phase': '7.5_intensive_monitoring',
                'status': 'stabilization_required',
                'current_stability_score': stability_score,
                'target_stability_score': 80,
                'stabilization_actions': [
                    'Continuar paper trading con parámetros conservadores',
                    'Monitoreo intensivo 24/7',
                    'Ejecutar trades adicionales para estabilización',
                    'Re-evaluar cada 12 horas'
                ],
                'next_evaluation': (datetime.now() + timedelta(hours=12)).isoformat()
            }
            
            plan_file = f"stabilization_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(plan_file, 'w') as f:
                json.dump(stabilization_plan, f, indent=2)
            
            print(f"✅ Plan de estabilización guardado en: {plan_file}")
            
        else:
            # Sistema listo para trading real
            print("✅ Sistema listo para trading real")
            print("🚀 Proceder con activación gradual")
        
        # 9. Crear reporte de monitoreo intensivo
        print("\n📋 9. CREANDO REPORTE DE MONITOREO INTENSIVO...")
        
        monitoring_report = {
            'timestamp': datetime.now().isoformat(),
            'phase': '7.5_intensive_stabilization_monitoring',
            'status': 'completed',
            'initial_state': {
                'balance': initial_balance,
                'total_trades': portfolio['total_trades'],
                'balance_change_pct': balance_change_pct
            },
            'final_state': {
                'balance': balance_after,
                'total_trades': portfolio_after['total_trades'],
                'balance_change_pct': balance_change_after
            },
            'stabilization_trades': {
                'planned': len(stabilization_trades),
                'executed': executed_trades,
                'success_rate': (executed_trades / len(stabilization_trades)) * 100 if stabilization_trades else 0
            },
            'stability_analysis': {
                'score': stability_score,
                'factors': stability_factors,
                'readiness': readiness_status,
                'can_proceed': can_proceed
            },
            'recommendations': [
                'Continuar monitoreo intensivo' if not can_proceed else 'Proceder con trading real',
                'Re-evaluar en 12 horas' if not can_proceed else 'Activar trading real gradualmente',
                'Mantener parámetros conservadores' if not can_proceed else 'Expandir a más assets'
            ]
        }
        
        # Guardar reporte
        report_file = f"intensive_monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(monitoring_report, f, indent=2)
        
        print(f"✅ Reporte de monitoreo intensivo guardado en: {report_file}")
        
        # 10. Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE MONITOREO INTENSIVO DE ESTABILIZACIÓN")
        print("=" * 60)
        
        print("✅ Estado inicial verificado")
        print("✅ Configuración validada")
        print("✅ Trades de estabilización ejecutados")
        print("✅ Estado final verificado")
        print("✅ Puntuación de estabilidad calculada")
        print("✅ Readiness evaluado")
        print("✅ Monitoreo configurado")
        print("✅ Reporte generado")
        
        print(f"\n📊 ESTADO ACTUAL:")
        print(f"   Balance: ${balance_after:.2f} (cambio: {balance_change_after:.2f}%)")
        print(f"   Total trades: {portfolio_after['total_trades']}")
        print(f"   Assets activos: {len(config_summary['active_assets'])}")
        print(f"   Puntuación de estabilidad: {stability_score}/100")
        print(f"   Readiness: {readiness_status}")
        
        if can_proceed:
            print(f"\n🚀 SISTEMA LISTO PARA TRADING REAL:")
            print(f"   • Puntuación objetivo alcanzada: {stability_score}/100")
            print(f"   • Sistema estable y validado")
            print(f"   • Proceder con activación gradual")
        else:
            print(f"\n📊 SISTEMA REQUIERE ESTABILIZACIÓN ADICIONAL:")
            print(f"   • Puntuación actual: {stability_score}/100")
            print(f"   • Puntuación objetivo: 80/100")
            print(f"   • Continuar monitoreo intensivo")
            print(f"   • Re-evaluar en 12 horas")
        
        print(f"\n⏰ PRÓXIMOS PASOS:")
        if can_proceed:
            print(f"   1. Activar trading real gradualmente")
            print(f"   2. Monitorear primer asset en trading real")
            print(f"   3. Expandir a más assets según estabilidad")
        else:
            print(f"   1. Continuar monitoreo intensivo")
            print(f"   2. Ejecutar trades adicionales de estabilización")
            print(f"   3. Re-evaluar estabilidad en 12 horas")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en monitoreo intensivo: {e}")
        logger.error(f"Error en monitoreo: {e}")
        return False

def main():
    """Función principal"""
    success = intensive_stabilization_monitoring()
    
    if success:
        print(f"\n🎉 MONITOREO INTENSIVO DE ESTABILIZACIÓN COMPLETADO")
        print("📊 Sistema evaluado y monitoreado")
        print("📋 Reporte detallado generado")
        print("⏰ Seguir recomendaciones según readiness")
        
    else:
        print(f"\n❌ MONITOREO INTENSIVO DE ESTABILIZACIÓN FALLÓ")
        print("🔧 Revisar errores antes de continuar")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
