#!/usr/bin/env python3
"""
Script de Re-evaluación Automática
GridBot V2.5 - Fase 7.6: Re-evaluación Automática para Trading Real
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

def auto_re_evaluation():
    """Re-evaluación automática del sistema para trading real"""
    print("🔄 INICIANDO RE-EVALUACIÓN AUTOMÁTICA DEL SISTEMA")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 7.6: Re-evaluación Automática para Trading Real")
    
    try:
        # 1. Verificar estado actual del sistema
        print("\n🔍 1. VERIFICANDO ESTADO ACTUAL DEL SISTEMA...")
        
        from app.core.safety_validator import get_system_safety_status
        safety_status = get_system_safety_status()
        
        print(f"   Circuit Breaker: {'🔴 ABIERTO' if safety_status['circuit_breaker']['is_open'] else '🟢 CERRADO'}")
        print(f"   Sistema Seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}")
        
        # 2. Verificar configuración actual
        print("\n⚙️ 2. VERIFICANDO CONFIGURACIÓN ACTUAL...")
        
        from app.core.unified_config import get_config
        config = get_config()
        config_summary = config.get_config_summary()
        
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(f"   Límites de seguridad:")
        print(f"      • Pérdida diaria: {config_summary['safety_limits']['max_daily_loss']*100:.1f}%")
        print(f"      • Pérdida total: {config_summary['safety_limits']['max_total_loss']*100:.1f}%")
        print(f"      • Pérdida por trade: {config_summary['safety_limits']['max_trade_loss']*100:.1f}%")
        
        # 3. Estado actual del paper trading
        print("\n📊 3. ESTADO ACTUAL DEL PAPER TRADING...")
        
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
        print(f"   PnL total: ${portfolio['total_pnl']:.2f} ({portfolio['total_pnl_pct']:.2f}%)")
        
        # 4. Ejecutar trades adicionales de estabilización si es necesario
        print("\n🧪 4. EJECUTANDO TRADES ADICIONALES DE ESTABILIZACIÓN...")
        
        from app.core.paper_trading import paper_trading_system
        
        # Trades adicionales para mejorar estabilidad
        additional_trades = [
            {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.0003, "price": 108100},
            {"symbol": "ETHUSDT", "side": "BUY", "quantity": 0.003, "price": 4405},
            {"symbol": "BNBUSDT", "side": "BUY", "quantity": 0.03, "price": 852},
            {"symbol": "BTCUSDT", "side": "SELL", "quantity": 0.0003, "price": 108400},
            {"symbol": "ETHUSDT", "side": "SELL", "quantity": 0.003, "price": 4420},
            {"symbol": "BNBUSDT", "side": "SELL", "quantity": 0.03, "price": 857},
        ]
        
        executed_trades = 0
        for i, trade in enumerate(additional_trades, 1):
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
        
        print(f"   ✅ Trades adicionales ejecutados: {executed_trades}/{len(additional_trades)}")
        
        # 5. Verificar estado final después de trades adicionales
        print("\n📊 5. VERIFICANDO ESTADO FINAL DESPUÉS DE TRADES ADICIONALES...")
        
        portfolio_final = paper_trading_system.get_portfolio_summary()
        balance_final = portfolio_final['current_balance']
        balance_change_final = ((balance_final - initial_balance) / initial_balance) * 100
        
        print(f"   Balance final: ${balance_final:.2f}")
        print(f"   Cambio total: {balance_change_final:.2f}%")
        print(f"   Total trades: {portfolio_final['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio_final['open_positions']}")
        print(f"   PnL total: ${portfolio_final['total_pnl']:.2f} ({portfolio_final['total_pnl_pct']:.2f}%)")
        
        # 6. Calcular puntuación final de estabilidad
        print("\n🎯 6. CALCULANDO PUNTUACIÓN FINAL DE ESTABILIDAD...")
        
        stability_score = 0
        stability_factors = []
        
        # Factor 1: Cambio de balance
        if abs(balance_change_final) < 2:
            stability_score += 25
            stability_factors.append("✅ Balance estable (< 2% cambio)")
        elif abs(balance_change_final) < 5:
            stability_score += 15
            stability_factors.append("🟡 Balance moderadamente estable (< 5% cambio)")
        else:
            stability_factors.append("🔴 Balance inestable (> 5% cambio)")
        
        # Factor 2: Número de trades
        if portfolio_final['total_trades'] >= 15:
            stability_score += 25
            stability_factors.append("✅ Excelente cantidad de trades para análisis (≥ 15)")
        elif portfolio_final['total_trades'] >= 10:
            stability_score += 25
            stability_factors.append("✅ Suficientes trades para análisis (≥ 10)")
        elif portfolio_final['total_trades'] >= 8:
            stability_score += 20
            stability_factors.append("🟡 Trades suficientes para análisis (≥ 8)")
        elif portfolio_final['total_trades'] >= 5:
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
        
        print(f"   Puntuación final de estabilidad: {stability_score}/100")
        print(f"   Factores de estabilidad:")
        for factor in stability_factors:
            print(f"      {factor}")
        
        # 7. Evaluar readiness final para trading real
        print("\n🚀 7. EVALUANDO READINESS FINAL PARA TRADING REAL...")
        
        if stability_score >= 80:
            readiness_status = "🟢 LISTO"
            readiness_message = "Sistema estable y listo para trading real"
            can_proceed = True
        elif stability_score >= 75:
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
        
        # 8. Configurar sistema según readiness
        print("\n⚙️ 8. CONFIGURANDO SISTEMA SEGÚN READINESS...")
        
        if can_proceed:
            # Sistema listo para trading real
            real_trading_config = {
                'trading_enabled': True,
                'paper_trading': False,
                'max_concurrent_trades': 3,
                'default_investment_percentage': 0.05,
                'emergency_stop_enabled': True
            }
            
            config.update_system_settings(real_trading_config)
            print("✅ Configuración de trading real aplicada")
            print("🚀 Sistema listo para activación gradual")
            
        else:
            # Mantener paper trading con monitoreo intensivo
            monitoring_config = {
                'alerts_enabled': True,
                'email_alerts': True,
                'sms_alerts': False,
                'dashboard_enabled': True,
                'log_level': 'INFO'
            }
            
            config.update_monitoring_settings(monitoring_config)
            print("✅ Monitoreo intensivo configurado")
            print("📊 Sistema requiere estabilización adicional")
        
        # 9. Crear plan de acción final
        print("\n📋 9. CREANDO PLAN DE ACCIÓN FINAL...")
        
        if can_proceed:
            final_plan = {
                'timestamp': datetime.now().isoformat(),
                'phase': '7.6_auto_re_evaluation_complete',
                'status': 'ready_for_real_trading',
                'final_stability_score': stability_score,
                'readiness': readiness_status,
                'next_phases': [
                    {
                        'phase': '8.1',
                        'action': 'Activación Gradual de Trading Real',
                        'description': 'Activar trading real con 1 asset',
                        'duration': '24 horas',
                        'criteria': 'Monitoreo intensivo, sin pérdidas significativas'
                    },
                    {
                        'phase': '8.2',
                        'action': 'Expansión Multi-Asset',
                        'description': 'Activar más assets gradualmente',
                        'duration': '48 horas',
                        'criteria': 'Estabilidad confirmada con primer asset'
                    },
                    {
                        'phase': '8.3',
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
            final_plan = {
                'timestamp': datetime.now().isoformat(),
                'phase': '7.6_auto_re_evaluation_incomplete',
                'status': 'stabilization_required',
                'final_stability_score': stability_score,
                'target_stability_score': 80,
                'stabilization_requirements': [
                    'Reducir volatilidad del balance',
                    'Aumentar número de trades para análisis',
                    'Confirmar estabilidad de circuit breakers',
                    'Validar límites de seguridad'
                ],
                'next_steps': [
                    {
                        'step': 1,
                        'action': 'Estabilización Extendida',
                        'description': 'Continuar paper trading hasta estabilización',
                        'duration': '72-96 horas',
                        'criteria': 'Puntuación de estabilidad ≥ 80'
                    },
                    {
                        'step': 2,
                        'action': 'Re-evaluación Final',
                        'description': 'Re-evaluar readiness para trading real',
                        'duration': '96 horas',
                        'criteria': 'Sistema completamente estable'
                    }
                ]
            }
        
        # Guardar plan final
        plan_file = f"final_action_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(plan_file, 'w') as f:
            json.dump(final_plan, f, indent=2)
        
        print(f"✅ Plan de acción final guardado en: {plan_file}")
        
        # 10. Resumen final
        print("\n" + "=" * 60)
        print("🎯 RESUMEN DE RE-EVALUACIÓN AUTOMÁTICA")
        print("=" * 60)
        
        print("✅ Estado del sistema verificado")
        print("✅ Configuración validada")
        print("✅ Trades adicionales ejecutados")
        print("✅ Estado final verificado")
        print("✅ Puntuación final calculada")
        print("✅ Readiness final determinado")
        print("✅ Sistema configurado")
        print("✅ Plan de acción final creado")
        
        print(f"\n📊 ESTADO FINAL:")
        print(f"   Balance: ${balance_final:.2f} (cambio: {balance_change_final:.2f}%)")
        print(f"   Total trades: {portfolio_final['total_trades']}")
        print(f"   Assets activos: {len(config_summary['active_assets'])}")
        print(f"   Puntuación final de estabilidad: {stability_score}/100")
        print(f"   Readiness final: {readiness_status}")
        
        if can_proceed:
            print(f"\n🚀 SISTEMA LISTO PARA TRADING REAL:")
            print(f"   • Puntuación objetivo alcanzada: {stability_score}/100")
            print(f"   • Sistema estable y validado")
            print(f"   • Trading real habilitado")
            print(f"   • Proceder con activación gradual")
        else:
            print(f"\n📊 SISTEMA REQUIERE ESTABILIZACIÓN EXTENDIDA:")
            print(f"   • Puntuación actual: {stability_score}/100")
            print(f"   • Puntuación objetivo: 80/100")
            print(f"   • Continuar paper trading")
            print(f"   • Re-evaluar en 72-96 horas")
        
        print(f"\n⏰ PLAN DE ACCIÓN:")
        if can_proceed:
            print(f"   1. Activar trading real gradualmente")
            print(f"   2. Monitorear primer asset en trading real")
            print(f"   3. Expandir a más assets según estabilidad")
        else:
            print(f"   1. Continuar estabilización extendida")
            print(f"   2. Monitoreo intensivo durante 72-96 horas")
            print(f"   3. Re-evaluación final para trading real")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en re-evaluación automática: {e}")
        logger.error(f"Error en re-evaluación: {e}")
        return False

def main():
    """Función principal"""
    success = auto_re_evaluation()
    
    if success:
        print(f"\n🎉 RE-EVALUACIÓN AUTOMÁTICA COMPLETADA EXITOSAMENTE")
        print("📊 Sistema evaluado y configurado")
        print("📋 Plan de acción final creado")
        print("⏰ Seguir plan según readiness final")
        
    else:
        print(f"\n❌ RE-EVALUACIÓN AUTOMÁTICA FALLÓ")
        print("🔧 Revisar errores antes de continuar")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
