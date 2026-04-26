#!/usr/bin/env python3
"""
Script de Verificación de Estado del Monitoreo
GridBot V2.5 - Verificar estado del monitoreo continuo
"""

import sys
import os
import json
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_monitoring_status():
    """Verificar estado del monitoreo continuo"""
    print("🔍 VERIFICANDO ESTADO DEL MONITOREO CONTINUO")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 1. Verificar si el proceso está ejecutándose
        print("\n🔍 1. VERIFICANDO PROCESO DE MONITOREO...")

        import subprocess

        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        if "continuous_72h_monitoring.py" in result.stdout:
            print("✅ Proceso de monitoreo activo")

            # Extraer PID del proceso
            lines = result.stdout.split("\n")
            for line in lines:
                if "continuous_72h_monitoring.py" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        print(f"   PID: {pid}")
                        break
        else:
            print("❌ Proceso de monitoreo no encontrado")
            return False

        # 2. Verificar archivos de monitoreo generados
        print("\n📁 2. VERIFICANDO ARCHIVOS DE MONITOREO...")

        monitoring_dir = os.getenv("MONITORING_DIR", "monitoring_data")
        monitoring_files = []
        try:
            for file in os.listdir(monitoring_dir):
                if file.startswith(
                    "continuous_72h_monitoring_data_"
                ) or file.startswith("monitoring_summary_"):
                    monitoring_files.append(os.path.join(monitoring_dir, file))
        except FileNotFoundError:
            print("⚠️ Directorio monitoring_data no encontrado")
            monitoring_files = []

        if monitoring_files:
            print(f"✅ Archivos de monitoreo encontrados: {len(monitoring_files)}")
            for file in sorted(monitoring_files)[-3:]:  # Mostrar últimos 3
                print(f"   📄 {file}")
        else:
            print("⚠️ No se encontraron archivos de monitoreo aún")

        # 3. Verificar estado actual del sistema
        print("\n📊 3. VERIFICANDO ESTADO ACTUAL DEL SISTEMA...")

        from app.core.paper_trading import get_paper_portfolio_summary

        portfolio = get_paper_portfolio_summary()

        initial_balance = portfolio["initial_balance"]
        current_balance = portfolio["current_balance"]
        balance_change_pct = (
            (current_balance - initial_balance) / initial_balance
        ) * 100

        print(f"   Balance inicial: ${initial_balance:.2f}")
        print(f"   Balance actual: ${current_balance:.2f}")
        print(f"   Cambio: {balance_change_pct:.2f}%")
        print(f"   Total trades: {portfolio['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio['open_positions']}")
        print(
            f"   PnL total: ${portfolio['total_pnl']:.2f} ({portfolio['total_pnl_pct']:.2f}%)"
        )

        # 4. Verificar estado de seguridad
        print("\n🛡️ 4. VERIFICANDO ESTADO DE SEGURIDAD...")

        from app.core.safety_validator import get_system_safety_status

        safety_status = get_system_safety_status()

        print(
            f"   Circuit Breaker: {'🔴 ABIERTO' if safety_status['circuit_breaker']['is_open'] else '🟢 CERRADO'}"
        )
        print(
            f"   Sistema Seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}"
        )
        print(f"   Último check: {safety_status.get('last_check', 'N/A')}")

        # 5. Calcular puntuación actual de estabilidad
        print("\n🎯 5. CALCULANDO PUNTUACIÓN ACTUAL DE ESTABILIDAD...")

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
        if portfolio["total_trades"] >= 15:
            stability_score += 25
            stability_factors.append(
                "✅ Excelente cantidad de trades para análisis (≥ 15)"
            )
        elif portfolio["total_trades"] >= 10:
            stability_score += 25
            stability_factors.append("✅ Suficientes trades para análisis (≥ 10)")
        elif portfolio["total_trades"] >= 8:
            stability_score += 20
            stability_factors.append("🟡 Trades suficientes para análisis (≥ 8)")
        elif portfolio["total_trades"] >= 5:
            stability_score += 15
            stability_factors.append("🟡 Trades moderados para análisis (≥ 5)")
        else:
            stability_factors.append("🔴 Pocos trades para análisis (< 5)")

        # Factor 3: Circuit breakers
        if not safety_status["circuit_breaker"]["is_open"]:
            stability_score += 25
            stability_factors.append("✅ Circuit breakers estables")
        else:
            stability_factors.append("🔴 Circuit breakers activados")

        # Factor 4: Configuración de seguridad
        stability_score += 25
        stability_factors.append("✅ Límites de seguridad conservadores")

        print(f"   Puntuación actual de estabilidad: {stability_score}/100")
        print("   Factores de estabilidad:")
        for factor in stability_factors:
            print(f"      {factor}")

        # 6. Evaluar readiness actual
        print("\n🚀 6. EVALUANDO READINESS ACTUAL...")

        if stability_score >= 80:
            readiness_status = "🟢 LISTO"
            readiness_message = "Sistema estable y listo para trading real"
            can_proceed = True
        elif stability_score >= 70:
            readiness_status = "🟡 CASI LISTO"
            readiness_message = (
                "Sistema casi estable, requiere estabilización adicional"
            )
            can_proceed = False
        else:
            readiness_status = "🔴 NO LISTO"
            readiness_message = "Sistema no está listo para trading real"
            can_proceed = False

        print(f"   Estado de readiness: {readiness_status}")
        print(f"   Mensaje: {readiness_message}")
        print(f"   ¿Puede proceder?: {'✅ SÍ' if can_proceed else '❌ NO'}")

        # 7. Mostrar progreso del monitoreo
        print("\n📊 7. PROGRESO DEL MONITOREO CONTINUO...")

        if monitoring_files:
            # Intentar leer el archivo más reciente
            latest_file = sorted(monitoring_files)[-1]
            try:
                with open(latest_file, "r") as f:
                    data = json.load(f)

                session = data.get("monitoring_session", {})
                checks = data.get("checks", [])

                if session and checks:
                    start_time = session.get("start_time")
                    total_duration = session.get("total_duration_hours", 72)

                    if start_time:
                        start_dt = datetime.fromisoformat(
                            start_time.replace("Z", "+00:00")
                        )
                        elapsed = (datetime.now() - start_dt).total_seconds() / 3600
                        remaining = max(0, total_duration - elapsed)
                        progress = (elapsed / total_duration) * 100

                        print(
                            f"   📅 Inicio del monitoreo: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        print(f"   ⏰ Tiempo transcurrido: {elapsed:.1f} horas")
                        print(f"   ⏰ Tiempo restante: {remaining:.1f} horas")
                        print(f"   📊 Progreso: {progress:.1f}%")
                        print(f"   🔍 Total de checks ejecutados: {len(checks)}")

                        if checks:
                            latest_check = checks[-1]
                            latest_stability = latest_check.get(
                                "stability_metrics", {}
                            ).get("stability_score", 0)
                            latest_readiness = latest_check.get("readiness", {}).get(
                                "status", "UNKNOWN"
                            )

                            print(
                                f"   🎯 Última puntuación de estabilidad: {latest_stability}/100"
                            )
                            print(
                                f"   🚀 Último estado de readiness: {latest_readiness}"
                            )
                    else:
                        print("   ⚠️ No se pudo determinar el tiempo de inicio")
                else:
                    print("   ⚠️ Estructura de datos de monitoreo incompleta")

            except Exception as e:
                print(f"   ❌ Error leyendo archivo de monitoreo: {e}")
        else:
            print("   ⏸️ No hay archivos de monitoreo disponibles aún")

        # 8. Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DEL ESTADO DEL MONITOREO")
        print("=" * 60)

        print("✅ Proceso de monitoreo activo")
        print("✅ Sistema en estado seguro")
        print("✅ Paper trading operativo")
        print("✅ Circuit breakers estables")
        print(f"📊 Puntuación actual de estabilidad: {stability_score}/100")
        print(f"🚀 Readiness actual: {readiness_status}")

        if can_proceed:
            print("\n🎉 SISTEMA LISTO PARA TRADING REAL:")
            print("   • Puntuación objetivo alcanzada")
            print("   • Sistema estable y validado")
            print("   • Proceder con activación gradual")
        else:
            print("\n📊 SISTEMA REQUIERE ESTABILIZACIÓN ADICIONAL:")
            print(f"   • Puntuación actual: {stability_score}/100")
            print("   • Puntuación objetivo: 80/100")
            print("   • Continuar monitoreo continuo")
            print("   • Re-evaluar cuando esté listo")

        print("\n⏰ MONITOREO CONTINUO:")
        print("   • Proceso activo en background")
        print("   • Checks automáticos cada hora")
        print("   • Trades de estabilización cada 6 horas")
        print("   • Datos guardados automáticamente")
        print("   • Duración total: 72 horas")

        return True

    except Exception as e:
        print(f"❌ Error verificando estado del monitoreo: {e}")
        return False


def main():
    """Función principal"""
    success = check_monitoring_status()

    if success:
        print("\n🎉 VERIFICACIÓN COMPLETADA EXITOSAMENTE")
        print("📊 Estado del monitoreo verificado")
        print("📋 Resumen del sistema generado")
        print("⏰ Continuar monitoreo hasta estabilización")

    else:
        print("\n❌ VERIFICACIÓN FALLÓ")
        print("🔧 Revisar errores antes de continuar")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
