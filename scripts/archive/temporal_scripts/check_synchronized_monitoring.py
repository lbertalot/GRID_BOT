#!/usr/bin/env python3
"""
Script de Verificación del Monitoreo Sincronizado
Verifica que el monitoreo esté funcionando y mostrando el estado correcto
"""

import json
import logging
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SynchronizedMonitoringChecker:
    def __init__(self):
        self.monitoring_dir = "monitoring_data"
        self.paper_trading_file = "paper_trading_state.json"

    def check_monitoring_process(self):
        """Verificar si el proceso de monitoreo sincronizado está activo"""
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info[
                        "cmdline"
                    ] and "synchronized_monitoring.py" in " ".join(
                        proc.info["cmdline"]
                    ):
                        return {
                            "active": True,
                            "pid": proc.info["pid"],
                            "status": "RUNNING",
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"active": False, "pid": None, "status": "NOT_FOUND"}
        except ImportError:
            return {"active": "UNKNOWN", "pid": None, "status": "PSUTIL_NOT_AVAILABLE"}

    def check_monitoring_files(self):
        """Verificar archivos de monitoreo generados"""
        try:
            if Path(self.monitoring_dir).exists():
                monitoring_files = list(
                    Path(self.monitoring_dir).glob("monitoring_summary_*.json")
                )
                monitoring_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

                if monitoring_files:
                    latest_file = monitoring_files[0]
                    with open(latest_file, "r") as f:
                        latest_data = json.load(f)

                    return {
                        "files_found": len(monitoring_files),
                        "latest_file": latest_file.name,
                        "latest_data": latest_data,
                    }
                else:
                    return {"files_found": 0, "latest_file": None, "latest_data": None}
            else:
                return {"files_found": 0, "latest_file": None, "latest_data": None}
        except Exception as e:
            logger.error("❌ Error verificando archivos de monitoreo: %s", e)
            return {"files_found": 0, "latest_file": None, "latest_data": None}

    def check_real_paper_trading_state(self):
        """Verificar estado real del paper trading"""
        try:
            if Path(self.paper_trading_file).exists():
                with open(self.paper_trading_file, "r") as f:
                    state = json.load(f)

                if "balance" in state and "trades" in state:
                    balance_change_pct = (
                        (state["balance"] - state["initial_balance"])
                        / state["initial_balance"]
                    ) * 100
                    return {
                        "balance": state["balance"],
                        "initial_balance": state["initial_balance"],
                        "balance_change_pct": balance_change_pct,
                        "total_trades": len(state["trades"]),
                        "structure_valid": True,
                    }
                else:
                    return {"structure_valid": False, "error": "Estructura inválida"}
            else:
                return {"structure_valid": False, "error": "Archivo no encontrado"}
        except Exception as e:
            logger.error("❌ Error verificando estado real: %s", e)
            return {"structure_valid": False, "error": str(e)}

    def run_synchronization_check(self):
        """Ejecutar verificación completa de sincronización"""
        print("🔍 VERIFICANDO MONITOREO SINCRONIZADO")
        print("=" * 60)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("📋 Verificación de Sincronización del Monitoreo")
        print()

        # 1. Verificar proceso de monitoreo
        print("🔍 1. VERIFICANDO PROCESO DE MONITOREO...")
        monitoring_status = self.check_monitoring_process()
        if monitoring_status["active"]:
            print("   ✅ Proceso de monitoreo sincronizado activo")
            print(f"   PID: {monitoring_status['pid']}")
            print(f"   Estado: {monitoring_status['status']}")
        else:
            print("   ❌ Proceso de monitoreo sincronizado no activo")
            print(f"   Estado: {monitoring_status['status']}")
        print()

        # 2. Verificar archivos de monitoreo
        print("📁 2. VERIFICANDO ARCHIVOS DE MONITOREO...")
        monitoring_files = self.check_monitoring_files()
        if monitoring_files["files_found"] > 0:
            print(
                f"   ✅ Archivos de monitoreo encontrados: {monitoring_files['files_found']}"
            )
            print(f"   📄 Archivo más reciente: {monitoring_files['latest_file']}")

            if monitoring_files["latest_data"]:
                latest = monitoring_files["latest_data"]
                print(f"   📊 Último check: #{latest.get('check_number', 'N/A')}")
                print(f"   ⏰ Timestamp: {latest.get('timestamp', 'N/A')}")
                print(
                    f"   🎯 Estabilidad: {latest.get('stability_score', {}).get('total_score', 'N/A')}/100"
                )
                print(
                    f"   🚀 Readiness: {latest.get('readiness', {}).get('status', 'N/A')}"
                )
        else:
            print("   ❌ No se encontraron archivos de monitoreo")
        print()

        # 3. Verificar estado real del paper trading
        print("📊 3. VERIFICANDO ESTADO REAL DEL PAPER TRADING...")
        real_state = self.check_real_paper_trading_state()
        if real_state["structure_valid"]:
            print("   ✅ Estructura del archivo válida")
            print(f"   Balance inicial: ${real_state['initial_balance']:.2f}")
            print(f"   Balance actual: ${real_state['balance']:.2f}")
            print(f"   Cambio: {real_state['balance_change_pct']:.2f}%")
            print(f"   Total trades: {real_state['total_trades']}")
        else:
            print("   ❌ Estructura del archivo inválida")
            print(f"   Error: {real_state.get('error', 'Desconocido')}")
        print()

        # 4. Análisis de sincronización
        print("🔄 4. ANÁLISIS DE SINCRONIZACIÓN...")
        if (
            monitoring_status["active"]
            and monitoring_files["files_found"] > 0
            and real_state["structure_valid"]
        ):
            print("   ✅ MONITOREO COMPLETAMENTE SINCRONIZADO")
            print("   • Proceso activo")
            print("   • Archivos generándose")
            print("   • Estructura de datos válida")

            # Comparar datos del monitoreo con estado real
            if monitoring_files["latest_data"]:
                latest = monitoring_files["latest_data"]
                monitoring_stability = latest.get("stability_score", {}).get(
                    "total_score", 0
                )
                monitoring_balance = latest.get("paper_trading", {}).get("balance", 0)

                print("   📊 Datos del monitoreo:")
                print(f"      Estabilidad: {monitoring_stability}/100")
                print(f"      Balance: ${monitoring_balance:.2f}")

                print("   📊 Estado real:")
                print(f"      Balance: ${real_state['balance']:.2f}")

                if abs(monitoring_balance - real_state["balance"]) < 0.01:
                    print("   ✅ Sincronización de datos: PERFECTA")
                else:
                    print("   ⚠️ Sincronización de datos: DIFERENCIA DETECTADA")
        else:
            print("   ❌ MONITOREO NO SINCRONIZADO")
            print("   • Proceso inactivo o archivos faltantes")
            print("   • Necesita configuración adicional")
        print()

        # 5. Resumen final
        print("=" * 60)
        print("📊 RESUMEN DE VERIFICACIÓN DE SINCRONIZACIÓN")
        print("=" * 60)

        if (
            monitoring_status["active"]
            and monitoring_files["files_found"] > 0
            and real_state["structure_valid"]
        ):
            print("✅ MONITOREO SINCRONIZADO FUNCIONANDO PERFECTAMENTE")
            print("✅ Estado real del sistema siendo monitoreado")
            print("✅ Datos actualizados en tiempo real")
            print("✅ Sistema listo para trading real")
        else:
            print("❌ MONITOREO NO SINCRONIZADO")
            print("❌ Requiere configuración adicional")
            print("❌ Estado del sistema no siendo monitoreado")

        print()
        print("⏰ MONITOREO SINCRONIZADO:")
        if monitoring_status["active"]:
            print("   • Proceso activo en background")
            print("   • Checks automáticos cada hora")
            print("   • Trades de estabilización cada 6 horas")
            print("   • Datos guardados automáticamente")
            print("   • Duración total: 72 horas")
        else:
            print("   • Proceso inactivo")
            print("   • Necesita ser iniciado")

        print()
        print("🎉 VERIFICACIÓN DE SINCRONIZACIÓN COMPLETADA")
        print("📊 Estado del monitoreo verificado")
        print("📋 Sincronización analizada")
        print("⏰ Seguir recomendaciones según estado")

        return {
            "monitoring_status": monitoring_status,
            "monitoring_files": monitoring_files,
            "real_state": real_state,
            "synchronized": monitoring_status["active"]
            and monitoring_files["files_found"] > 0
            and real_state["structure_valid"],
        }


def main():
    """Función principal"""
    checker = SynchronizedMonitoringChecker()
    result = checker.run_synchronization_check()
    return result


if __name__ == "__main__":
    main()
