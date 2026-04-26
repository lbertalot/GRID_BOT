#!/usr/bin/env python3
"""
Script de Monitoreo Prolongado
GridBot V2.5 - Fase 7: Monitoreo Extendido de Rendimiento
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
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def monitor_extended_performance():
    """Monitorea el rendimiento extendido del sistema"""
    print("📊 INICIANDO MONITOREO PROLONGADO DEL SISTEMA")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 7.2: Monitoreo Extendido de Rendimiento")

    try:
        # 1. Verificar estado del sistema
        print("\n🔍 1. VERIFICANDO ESTADO DEL SISTEMA...")

        from app.core.safety_validator import get_system_safety_status

        safety_status = get_system_safety_status()

        print(
            f"   Circuit Breaker: {'🔴 ABIERTO' if safety_status['circuit_breaker']['is_open'] else '🟢 CERRADO'}"
        )
        print(
            f"   Sistema Seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}"
        )

        if not safety_status["system_safe"]:
            print("⚠️ Sistema no está en estado seguro")
            print("🔧 Considerar revisar antes de continuar")

        # 2. Verificar configuración multi-asset
        print("\n⚙️ 2. VERIFICANDO CONFIGURACIÓN MULTI-ASSET...")

        from app.core.unified_config import get_config

        config = get_config()
        config_summary = config.get_config_summary()

        print(f"   Assets totales: {config_summary['assets_summary']['total_assets']}")
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(f"   Assets activos: {', '.join(config_summary['active_assets'])}")

        # 3. Verificar estado del paper trading
        print("\n📄 3. VERIFICANDO ESTADO DEL PAPER TRADING...")

        from app.core.paper_trading import get_paper_portfolio_summary

        portfolio = get_paper_portfolio_summary()

        print(f"   Balance inicial: ${portfolio['initial_balance']:.2f}")
        print(f"   Balance actual: ${portfolio['current_balance']:.2f}")
        print(f"   Total trades: {portfolio['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio['open_positions']}")
        print(
            f"   PnL total: ${portfolio['total_pnl']:.2f} ({portfolio['total_pnl_pct']:.2f}%)"
        )

        # Mostrar posiciones detalladas
        if portfolio["positions"]:
            print("   📈 Posiciones abiertas:")
            for position in portfolio["positions"]:
                print(
                    f"      • {position['symbol']}: {position['quantity']} @ ${position['avg_price']:.2f}"
                )
                print(
                    f"        Valor: ${position['market_value']:.2f}, PnL: ${position['unrealized_pnl']:.2f}"
                )

        # 4. Verificar métricas de rendimiento
        print("\n📊 4. VERIFICANDO MÉTRICAS DE RENDIMIENTO...")

        from app.core.monitoring import get_monitoring_status

        monitoring_status = get_monitoring_status()

        print(f"   Estado del sistema: {monitoring_status['system_status']}")
        print(f"   Total trades: {monitoring_status['metrics']['total_trades']}")
        print(
            f"   Trades exitosos: {monitoring_status['metrics']['successful_trades']}"
        )
        print(f"   Trades fallidos: {monitoring_status['metrics']['failed_trades']}")
        print(f"   Profit total: ${monitoring_status['metrics']['total_profit']:.2f}")
        print(f"   Loss total: ${monitoring_status['metrics']['total_loss']:.2f}")

        # 5. Verificar circuit breakers
        print("\n🛡️ 5. VERIFICANDO CIRCUIT BREAKERS...")

        from app.core.circuit_breaker import circuit_breaker

        cb_status = circuit_breaker.get_status()

        print(f"   Estado: {'🔴 ABIERTO' if cb_status['is_open'] else '🟢 CERRADO'}")
        if cb_status["is_open"]:
            print(f"   Razón: {cb_status['reason']}")
            print(f"   Abierto desde: {cb_status['opened_at']}")

        print("   Límites configurados:")
        print(
            f"      • Pérdida diaria: {cb_status['limits']['daily_loss_limit']*100:.1f}%"
        )
        print(
            f"      • Pérdida total: {cb_status['limits']['total_loss_limit']*100:.1f}%"
        )
        print(
            f"      • Pérdida por trade: {cb_status['limits']['trade_loss_limit']*100:.1f}%"
        )
        print(
            f"      • Pérdidas consecutivas: {cb_status['limits']['consecutive_losses']}"
        )
        print(
            f"      • Pérdida por hora: {cb_status['limits']['hourly_loss_limit']*100:.1f}%"
        )

        print("   Estado actual:")
        print(
            f"      • Pérdida diaria: {cb_status['current_state']['daily_loss']*100:.2f}%"
        )
        print(
            f"      • Pérdida total: {cb_status['current_state']['total_loss']*100:.2f}%"
        )
        print(
            f"      • Pérdidas consecutivas: {cb_status['current_state']['consecutive_losses']}"
        )
        print(
            f"      • Pérdida por hora: {cb_status['current_state']['hourly_loss']*100:.2f}%"
        )

        # 6. Verificar sistema de alertas
        print("\n🚨 6. VERIFICANDO SISTEMA DE ALERTAS...")

        print(f"   Alertas totales: {monitoring_status['total_alerts']}")
        if monitoring_status["recent_alerts"]:
            print("   Alertas recientes:")
            for alert in monitoring_status["recent_alerts"][-3:]:  # Últimas 3 alertas
                print(f"      • {alert['timestamp']}: {alert['message']}")
        else:
            print("   ✅ Sin alertas recientes")

        # 7. Análisis de rendimiento
        print("\n📈 7. ANÁLISIS DE RENDIMIENTO...")

        # Calcular métricas de rendimiento
        initial_balance = portfolio["initial_balance"]
        current_balance = portfolio["current_balance"]
        total_trades = portfolio["total_trades"]

        if total_trades > 0:
            # Calcular métricas
            balance_change = current_balance - initial_balance
            balance_change_pct = (balance_change / initial_balance) * 100

            # Calcular trades por día (asumiendo 1 día de operación)
            trades_per_day = total_trades

            # Calcular eficiencia
            if portfolio["total_pnl"] > 0:
                efficiency = "🟢 POSITIVA"
            elif portfolio["total_pnl"] < 0:
                efficiency = "🔴 NEGATIVA"
            else:
                efficiency = "🟡 NEUTRA"

            print(
                f"   Cambio de balance: ${balance_change:.2f} ({balance_change_pct:.2f}%)"
            )
            print(f"   Trades por día: {trades_per_day}")
            print(f"   Eficiencia: {efficiency}")

            # Evaluar estabilidad
            if abs(balance_change_pct) < 2:
                stability = "🟢 MUY ESTABLE"
            elif abs(balance_change_pct) < 5:
                stability = "🟡 ESTABLE"
            else:
                stability = "🔴 INESTABLE"

            print(f"   Estabilidad: {stability}")

            # Recomendaciones
            print("\n💡 RECOMENDACIONES:")
            if balance_change_pct < -3:
                print("   ⚠️ Pérdidas significativas detectadas")
                print("   🔧 Revisar estrategia y parámetros")
                print("   🛡️ Verificar circuit breakers")
            elif balance_change_pct > 3:
                print("   ✅ Rendimiento positivo")
                print("   🔄 Considerar aumentar exposición gradualmente")
                print("   📊 Monitorear estabilidad")
            else:
                print("   ✅ Rendimiento estable")
                print("   🔄 Continuar monitoreo")
                print("   📈 Evaluar activación de más assets")

        # 8. Crear reporte de monitoreo
        print("\n📋 8. CREANDO REPORTE DE MONITOREO...")

        monitoring_report = {
            "timestamp": datetime.now().isoformat(),
            "phase": "7.2_extended_monitoring",
            "status": "completed",
            "system_health": {
                "circuit_breaker_open": cb_status["is_open"],
                "system_safe": safety_status["system_safe"],
                "monitoring_status": monitoring_status["system_status"],
            },
            "paper_trading_performance": {
                "initial_balance": portfolio["initial_balance"],
                "current_balance": portfolio["current_balance"],
                "total_trades": portfolio["total_trades"],
                "open_positions": portfolio["open_positions"],
                "total_pnl": portfolio["total_pnl"],
                "total_pnl_pct": portfolio["total_pnl_pct"],
            },
            "circuit_breaker_status": {
                "is_open": cb_status["is_open"],
                "reason": cb_status.get("reason"),
                "limits": cb_status["limits"],
                "current_state": cb_status["current_state"],
            },
            "active_assets": config_summary["active_assets"],
            "recommendations": [],
        }

        # Agregar recomendaciones basadas en el análisis
        if "balance_change_pct" in locals():
            if balance_change_pct < -3:
                monitoring_report["recommendations"].append(
                    "Revisar estrategia y parámetros"
                )
                monitoring_report["recommendations"].append(
                    "Verificar circuit breakers"
                )
            elif balance_change_pct > 3:
                monitoring_report["recommendations"].append(
                    "Considerar aumentar exposición gradualmente"
                )
                monitoring_report["recommendations"].append("Monitorear estabilidad")
            else:
                monitoring_report["recommendations"].append("Continuar monitoreo")
                monitoring_report["recommendations"].append(
                    "Evaluar activación de más assets"
                )

        # Guardar reporte
        report_file = f"extended_monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(monitoring_report, f, indent=2)

        print(f"✅ Reporte de monitoreo guardado en: {report_file}")

        # 9. Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DEL MONITOREO EXTENDIDO")
        print("=" * 60)

        print("✅ Estado del sistema verificado")
        print("✅ Configuración multi-asset validada")
        print("✅ Rendimiento del paper trading analizado")
        print("✅ Circuit breakers verificados")
        print("✅ Sistema de alertas validado")
        print("✅ Análisis de rendimiento completado")
        print("✅ Reporte de monitoreo creado")

        print("\n📊 ESTADO ACTUAL:")
        print(f"   Assets activos: {len(config_summary['active_assets'])}")
        print(f"   Balance: ${current_balance:.2f} (cambio: {balance_change_pct:.2f}%)")
        print(f"   Total trades: {total_trades}")
        print(
            f"   Circuit breaker: {'🔴 ABIERTO' if cb_status['is_open'] else '🟢 CERRADO'}"
        )
        print(
            f"   Sistema seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}"
        )

        return True

    except Exception as e:
        print(f"❌ Error en monitoreo extendido: {e}")
        logger.error(f"Error en monitoreo: {e}")
        return False


def main():
    """Función principal"""
    success = monitor_extended_performance()

    if success:
        print("\n🎉 MONITOREO EXTENDIDO COMPLETADO EXITOSAMENTE")
        print("📊 Sistema analizado y reportado")
        print("📋 Reporte detallado generado")
        print("⏰ Continuar monitoreo según plan")

    else:
        print("\n❌ MONITOREO EXTENDIDO FALLÓ")
        print("🔧 Revisar errores antes de continuar")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
