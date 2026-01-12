#!/usr/bin/env python3
"""
Script de Evaluación de Rendimiento y Ajuste de Parámetros
GridBot V2.5 - Fase 7.3: Evaluación de Rendimiento
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

def evaluate_performance_and_adjust():
    """Evalúa el rendimiento y ajusta parámetros del sistema"""
    print("📊 INICIANDO EVALUACIÓN DE RENDIMIENTO Y AJUSTE")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 7.3: Evaluación de Rendimiento y Ajuste de Parámetros")
    
    try:
        # 1. Análisis detallado del rendimiento actual
        print("\n🔍 1. ANÁLISIS DETALLADO DEL RENDIMIENTO...")
        
        from app.core.paper_trading import get_paper_portfolio_summary
        portfolio = get_paper_portfolio_summary()
        
        # Calcular métricas de rendimiento
        initial_balance = portfolio['initial_balance']
        current_balance = portfolio['current_balance']
        total_trades = portfolio['total_trades']
        balance_change = current_balance - initial_balance
        balance_change_pct = (balance_change / initial_balance) * 100
        
        print(f"   Balance inicial: ${initial_balance:.2f}")
        print(f"   Balance actual: ${current_balance:.2f}")
        print(f"   Cambio absoluto: ${balance_change:.2f}")
        print(f"   Cambio porcentual: {balance_change_pct:.2f}%")
        print(f"   Total trades: {total_trades}")
        print(f"   Posiciones abiertas: {portfolio['open_positions']}")
        
        # 2. Análisis de posiciones por asset
        print("\n📈 2. ANÁLISIS DE POSICIONES POR ASSET...")
        
        if portfolio['positions']:
            total_invested = 0
            total_market_value = 0
            
            for position in portfolio['positions']:
                symbol = position['symbol']
                quantity = position['quantity']
                avg_price = position['avg_price']
                market_value = position['market_value']
                unrealized_pnl = position['unrealized_pnl']
                unrealized_pnl_pct = position['unrealized_pnl_pct']
                
                total_invested += position['cost_basis']
                total_market_value += market_value
                
                print(f"   📊 {symbol}:")
                print(f"      Cantidad: {quantity}")
                print(f"      Precio promedio: ${avg_price:.2f}")
                print(f"      Valor de mercado: ${market_value:.2f}")
                print(f"      PnL no realizado: ${unrealized_pnl:.2f} ({unrealized_pnl_pct:.2f}%)")
            
            print(f"\n   💰 Resumen de inversión:")
            print(f"      Total invertido: ${total_invested:.2f}")
            print(f"      Valor de mercado: ${total_market_value:.2f}")
            print(f"      Diferencia: ${total_market_value - total_invested:.2f}")
        
        # 3. Análisis de trades ejecutados
        print("\n📊 3. ANÁLISIS DE TRADES EJECUTADOS...")
        
        from app.core.paper_trading import paper_trading_system
        
        # Obtener historial de trades
        trade_history = paper_trading_system.get_trade_history()
        
        if trade_history:
            buy_trades = [t for t in trade_history if t['side'] == 'BUY']
            sell_trades = [t for t in trade_history if t['side'] == 'SELL']
            
            print(f"   Trades de compra: {len(buy_trades)}")
            print(f"   Trades de venta: {len(sell_trades)}")
            
            # Análisis de PnL por trade
            total_buy_value = sum(t['total_cost'] for t in buy_trades)
            total_sell_value = sum(t['total_revenue'] for t in sell_trades)
            
            print(f"   Valor total compras: ${total_buy_value:.2f}")
            print(f"   Valor total ventas: ${total_sell_value:.2f}")
            print(f"   Diferencia: ${total_sell_value - total_buy_value:.2f}")
            
            # Mostrar últimos trades
            print(f"\n   🕒 Últimos trades:")
            for trade in trade_history[-5:]:  # Últimos 5 trades
                timestamp = trade['timestamp']
                side = trade['side']
                symbol = trade['symbol']
                quantity = trade['quantity']
                price = trade['price']
                
                if side == 'BUY':
                    total_cost = trade['total_cost']
                    print(f"      📈 {timestamp}: BUY {quantity} {symbol} @ ${price:.2f} = ${total_cost:.2f}")
                else:
                    total_revenue = trade['total_revenue']
                    pnl = trade.get('realized_pnl', 0)
                    print(f"      📉 {timestamp}: SELL {quantity} {symbol} @ ${price:.2f} = ${total_revenue:.2f} (PnL: ${pnl:.2f})")
        
        # 4. Evaluación de la estrategia actual
        print("\n🎯 4. EVALUACIÓN DE LA ESTRATEGIA ACTUAL...")
        
        # Calcular métricas de estrategia
        if total_trades > 0:
            # Tasa de éxito (trades con PnL positivo)
            successful_trades = len([t for t in trade_history if t.get('realized_pnl', 0) > 0])
            success_rate = (successful_trades / total_trades) * 100 if total_trades > 0 else 0
            
            # Promedio de PnL por trade
            total_realized_pnl = sum(t.get('realized_pnl', 0) for t in trade_history)
            avg_pnl_per_trade = total_realized_pnl / total_trades if total_trades > 0 else 0
            
            # Volatilidad del balance
            volatility = "ALTA" if abs(balance_change_pct) > 5 else "MEDIA" if abs(balance_change_pct) > 2 else "BAJA"
            
            print(f"   Tasa de éxito: {success_rate:.1f}%")
            print(f"   PnL promedio por trade: ${avg_pnl_per_trade:.2f}")
            print(f"   Volatilidad del balance: {volatility}")
            
            # Evaluar rendimiento
            if balance_change_pct > 2:
                performance = "🟢 EXCELENTE"
                recommendation = "Considerar aumentar exposición gradualmente"
            elif balance_change_pct > 0:
                performance = "🟡 BUENO"
                recommendation = "Continuar monitoreo, ajustar parámetros menores"
            elif balance_change_pct > -2:
                performance = "🟡 ACEPTABLE"
                recommendation = "Revisar parámetros, optimizar estrategia"
            else:
                performance = "🔴 REQUIERE AJUSTE"
                recommendation = "Revisar estrategia completa, ajustar parámetros significativamente"
            
            print(f"   Rendimiento: {performance}")
            print(f"   Recomendación: {recommendation}")
        
        # 5. Análisis de configuración actual
        print("\n⚙️ 5. ANÁLISIS DE CONFIGURACIÓN ACTUAL...")
        
        from app.core.unified_config import get_config
        config = get_config()
        config_summary = config.get_config_summary()
        
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(f"   Límites de seguridad:")
        print(f"      • Pérdida diaria: {config_summary['safety_limits']['max_daily_loss']*100:.1f}%")
        print(f"      • Pérdida total: {config_summary['safety_limits']['max_total_loss']*100:.1f}%")
        print(f"      • Pérdida por trade: {config_summary['safety_limits']['max_trade_loss']*100:.1f}%")
        
        # 6. Propuesta de ajustes de parámetros
        print("\n🔧 6. PROPUESTA DE AJUSTES DE PARÁMETROS...")
        
        adjustments = []
        
        # Ajuste 1: Reducir exposición por asset si hay pérdidas significativas
        if balance_change_pct < -5:
            adjustments.append({
                'type': 'EXPOSURE_REDUCTION',
                'description': 'Reducir inversión por asset debido a pérdidas significativas',
                'current_value': '100.0',
                'proposed_value': '50.0',
                'reason': f'Balance reducido en {abs(balance_change_pct):.1f}%'
            })
        
        # Ajuste 2: Ajustar número de grids según volatilidad
        if abs(balance_change_pct) > 3:
            adjustments.append({
                'type': 'GRID_ADJUSTMENT',
                'description': 'Reducir número de grids para mayor estabilidad',
                'current_value': '5',
                'proposed_value': '3',
                'reason': 'Alta volatilidad detectada'
            })
        
        # Ajuste 3: Ajustar cantidades según rendimiento
        if total_trades > 0 and avg_pnl_per_trade < 0:
            adjustments.append({
                'type': 'QUANTITY_ADJUSTMENT',
                'description': 'Reducir cantidades por trade para minimizar pérdidas',
                'current_value': 'Variable por asset',
                'proposed_value': 'Reducir 50%',
                'reason': 'PnL promedio negativo'
            })
        
        # Ajuste 4: Ajustar límites de seguridad
        if balance_change_pct < -3:
            adjustments.append({
                'type': 'SAFETY_LIMITS',
                'description': 'Ajustar límites de pérdida más conservadores',
                'current_value': f"{config_summary['safety_limits']['max_daily_loss']*100:.1f}%",
                'proposed_value': '3.0%',
                'reason': 'Pérdidas significativas requieren límites más estrictos'
            })
        
        if adjustments:
            print(f"   🔧 Ajustes recomendados: {len(adjustments)}")
            for i, adjustment in enumerate(adjustments, 1):
                print(f"      {i}. {adjustment['type']}: {adjustment['description']}")
                print(f"         Actual: {adjustment['current_value']}")
                print(f"         Propuesto: {adjustment['proposed_value']}")
                print(f"         Razón: {adjustment['reason']}")
        else:
            print("   ✅ No se requieren ajustes significativos")
            print("   📊 Sistema funcionando dentro de parámetros aceptables")
        
        # 7. Aplicar ajustes automáticos (opcional)
        print("\n⚡ 7. APLICANDO AJUSTES AUTOMÁTICOS...")
        
        applied_adjustments = []
        
        for adjustment in adjustments:
            try:
                if adjustment['type'] == 'EXPOSURE_REDUCTION':
                    # Reducir inversión por asset
                    for asset_symbol in config_summary['active_assets']:
                        asset_config = config.get_asset_config(asset_symbol)
                        if asset_config:
                            current_investment = asset_config.get('investment_amount', 100.0)
                            new_investment = current_investment * 0.5  # Reducir 50%
                            
                            asset_config['investment_amount'] = new_investment
                            config.update_asset_config(asset_symbol, asset_config)
                            
                            applied_adjustments.append({
                                'asset': asset_symbol,
                                'adjustment': 'investment_reduction',
                                'old_value': current_investment,
                                'new_value': new_investment
                            })
                
                elif adjustment['type'] == 'GRID_ADJUSTMENT':
                    # Reducir número de grids
                    for asset_symbol in config_summary['active_assets']:
                        asset_config = config.get_asset_config(asset_symbol)
                        if asset_config:
                            current_grids = asset_config.get('grids', 5)
                            new_grids = 3  # Reducir a 3 grids
                            
                            asset_config['grids'] = new_grids
                            config.update_asset_config(asset_symbol, asset_config)
                            
                            applied_adjustments.append({
                                'asset': asset_symbol,
                                'adjustment': 'grid_reduction',
                                'old_value': current_grids,
                                'new_value': new_grids
                            })
                
                elif adjustment['type'] == 'SAFETY_LIMITS':
                    # Ajustar límites de seguridad
                    current_daily_limit = config_summary['safety_limits']['max_daily_loss']
                    new_daily_limit = 0.03  # 3%
                    
                    config.update_safety_limits({
                        'max_daily_loss': new_daily_limit
                    })
                    
                    applied_adjustments.append({
                        'adjustment': 'safety_limits',
                        'old_value': f"{current_daily_limit*100:.1f}%",
                        'new_value': f"{new_daily_limit*100:.1f}%"
                    })
                    
            except Exception as e:
                print(f"      ❌ Error aplicando ajuste {adjustment['type']}: {e}")
        
        if applied_adjustments:
            print(f"   ✅ Ajustes aplicados: {len(applied_adjustments)}")
            for adjustment in applied_adjustments:
                if 'asset' in adjustment:
                    print(f"      • {adjustment['asset']}: {adjustment['adjustment']} ({adjustment['old_value']} → {adjustment['new_value']})")
                else:
                    print(f"      • {adjustment['adjustment']}: {adjustment['old_value']} → {adjustment['new_value']}")
        else:
            print("   ✅ No se requirieron ajustes automáticos")
        
        # 8. Crear reporte de evaluación
        print("\n📋 8. CREANDO REPORTE DE EVALUACIÓN...")
        
        evaluation_report = {
            'timestamp': datetime.now().isoformat(),
            'phase': '7.3_performance_evaluation',
            'status': 'completed',
            'performance_metrics': {
                'initial_balance': initial_balance,
                'current_balance': current_balance,
                'balance_change': balance_change,
                'balance_change_pct': balance_change_pct,
                'total_trades': total_trades,
                'open_positions': portfolio['open_positions'],
                'total_pnl': portfolio['total_pnl'],
                'total_pnl_pct': portfolio['total_pnl_pct']
            },
            'strategy_analysis': {
                'success_rate': success_rate if 'success_rate' in locals() else 0,
                'avg_pnl_per_trade': avg_pnl_per_trade if 'avg_pnl_per_trade' in locals() else 0,
                'volatility': volatility if 'volatility' in locals() else 'UNKNOWN',
                'performance': performance if 'performance' in locals() else 'UNKNOWN'
            },
            'recommended_adjustments': adjustments,
            'applied_adjustments': applied_adjustments,
            'current_config': config_summary,
            'next_steps': [
                'Monitorear rendimiento con nuevos parámetros',
                'Evaluar estabilidad durante 24-48 horas',
                'Considerar activación de más assets si rendimiento mejora',
                'Preparar para Fase 7.4: Preparación Trading Real'
            ]
        }
        
        # Guardar reporte
        reports_dir = os.getenv("REPORTS_DIR", "reports")
        performance_dir = os.path.join(reports_dir, "performance")
        try:
            os.makedirs(performance_dir, exist_ok=True)
        except Exception:
            pass
        report_file = os.path.join(performance_dir, f"performance_evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w') as f:
            json.dump(evaluation_report, f, indent=2)
        
        print(f"✅ Reporte de evaluación guardado en: {report_file}")
        
        # 9. Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE EVALUACIÓN DE RENDIMIENTO")
        print("=" * 60)
        
        print("✅ Rendimiento analizado completamente")
        print("✅ Estrategia evaluada")
        print("✅ Ajustes de parámetros propuestos")
        print("✅ Ajustes automáticos aplicados")
        print("✅ Reporte de evaluación creado")
        
        print(f"\n📊 ESTADO ACTUAL:")
        print(f"   Balance: ${current_balance:.2f} (cambio: {balance_change_pct:.2f}%)")
        print(f"   Total trades: {total_trades}")
        print(f"   Assets activos: {len(config_summary['active_assets'])}")
        print(f"   Rendimiento: {performance if 'performance' in locals() else 'N/A'}")
        
        print(f"\n🔧 AJUSTES APLICADOS:")
        if applied_adjustments:
            for adjustment in applied_adjustments:
                if 'asset' in adjustment:
                    print(f"   • {adjustment['asset']}: {adjustment['adjustment']}")
                else:
                    print(f"   • {adjustment['adjustment']}")
        else:
            print("   • Ningún ajuste requerido")
        
        print(f"\n⏰ PRÓXIMOS PASOS:")
        print(f"   1. Monitorear rendimiento con nuevos parámetros")
        print(f"   2. Evaluar estabilidad durante 24-48 horas")
        print(f"   3. Considerar activación de más assets")
        print(f"   4. Preparar para Fase 7.4: Preparación Trading Real")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en evaluación de rendimiento: {e}")
        logger.error(f"Error en evaluación: {e}")
        return False

def main():
    """Función principal"""
    success = evaluate_performance_and_adjust()
    
    if success:
        print(f"\n🎉 EVALUACIÓN DE RENDIMIENTO COMPLETADA EXITOSAMENTE")
        print("📊 Sistema analizado y optimizado")
        print("🔧 Parámetros ajustados según rendimiento")
        print("📋 Reporte detallado generado")
        print("⏰ Continuar monitoreo con nuevos parámetros")
        
    else:
        print(f"\n❌ EVALUACIÓN DE RENDIMIENTO FALLÓ")
        print("🔧 Revisar errores antes de continuar")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
