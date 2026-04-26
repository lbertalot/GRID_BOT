#!/usr/bin/env python3
"""
Test de Componentes de Integridad - GridBot v2.5
Script para validar que todos los componentes de integridad funcionen correctamente
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.balance_validator import BalanceValidator
from app.core.operation_tracker import OperationTracker, OperationStatus
from app.core.integrity_monitor import IntegrityMonitor
from decimal import Decimal

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IntegrityComponentsTester:
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_status": "PENDING",
        }

    async def run_all_tests(self):
        """Ejecutar todas las pruebas de integridad"""
        logger.info("🚀 Iniciando pruebas de componentes de integridad")

        try:
            # Test 1: BalanceValidator
            await self.test_balance_validator()

            # Test 2: OperationTracker
            await self.test_operation_tracker()

            # Test 3: IntegrityMonitor
            await self.test_integrity_monitor()

            # Test 4: Integración entre componentes
            await self.test_component_integration()

            # Evaluar resultados generales
            await self.evaluate_overall_results()

            # Generar reporte
            await self.generate_test_report()

        except Exception as e:
            logger.error(f"❌ Error ejecutando pruebas: {e}")
            self.test_results["overall_status"] = "ERROR"
            self.test_results["error"] = str(e)

    async def test_balance_validator(self):
        """Probar BalanceValidator"""
        logger.info("🔍 Probando BalanceValidator...")

        try:
            # Crear instancia
            validator = BalanceValidator()

            # Verificar inicialización
            assert validator.alert_threshold == Decimal(
                "0.01"
            ), "Umbral de alerta incorrecto"
            assert validator.critical_threshold == Decimal(
                "0.05"
            ), "Umbral crítico incorrecto"
            assert (
                validator.check_interval == 900
            ), "Intervalo de verificación incorrecto"

            # Verificar métodos disponibles
            assert hasattr(
                validator, "validate_balances"
            ), "Método validate_balances no encontrado"
            assert hasattr(
                validator, "get_validation_summary"
            ), "Método get_validation_summary no encontrado"
            assert hasattr(
                validator, "force_validation"
            ), "Método force_validation no encontrado"

            # Verificar estado inicial
            summary = await validator.get_validation_summary()
            assert (
                "integrity_score" in summary
            ), "Campo integrity_score no encontrado en summary"
            assert (
                "total_validations" in summary
            ), "Campo total_validations no encontrado en summary"

            self.test_results["tests"]["balance_validator"] = {
                "status": "PASSED",
                "details": "BalanceValidator inicializado correctamente con todos los métodos requeridos",
                "integrity_score": summary.get("integrity_score"),
                "total_validations": summary.get("total_validations"),
            }

            logger.info("✅ BalanceValidator: PASSED")

        except Exception as e:
            logger.error(f"❌ BalanceValidator: FAILED - {e}")
            self.test_results["tests"]["balance_validator"] = {
                "status": "FAILED",
                "error": str(e),
            }

    async def test_operation_tracker(self):
        """Probar OperationTracker"""
        logger.info("🔍 Probando OperationTracker...")

        try:
            # Crear instancia
            tracker = OperationTracker()

            # Verificar inicialización
            assert tracker.track_slippage == True, "Tracking de slippage no habilitado"
            assert tracker.track_fees == True, "Tracking de fees no habilitado"
            assert (
                tracker.track_partial_fills == True
            ), "Tracking de partial fills no habilitado"
            assert (
                tracker.track_failed_operations == True
            ), "Tracking de operaciones fallidas no habilitado"

            # Verificar métodos disponibles
            assert hasattr(
                tracker, "track_operation"
            ), "Método track_operation no encontrado"
            assert hasattr(
                tracker, "update_operation_status"
            ), "Método update_operation_status no encontrado"
            assert hasattr(
                tracker, "get_operation_summary"
            ), "Método get_operation_summary no encontrado"
            assert hasattr(
                tracker, "get_failed_operations_summary"
            ), "Método get_failed_operations_summary no encontrado"

            # Verificar estado inicial
            summary = await tracker.get_operation_summary()
            assert (
                "total_operations" in summary
            ), "Campo total_operations no encontrado en summary"
            assert (
                "successful_operations" in summary
            ), "Campo successful_operations no encontrado en summary"
            assert (
                "failed_operations" in summary
            ), "Campo failed_operations no encontrado en summary"

            # Probar tracking de operación simulada
            test_operation = {
                "asset": "BTCUSDT",
                "type": "GRID_BUY",
                "side": "BUY",
                "quantity": 0.001,
                "price": 50000,
                "user_id": "test_user",
                "strategy_id": "test_strategy",
                "grid_level": 1,
            }

            operation_id = await tracker.track_operation(test_operation)
            assert operation_id is not None, "No se generó ID de operación"
            assert operation_id.startswith(
                "OP_"
            ), "Formato de ID de operación incorrecto"

            # Verificar que la operación se registró
            assert (
                operation_id in tracker.active_operations
            ), "Operación no se registró en operaciones activas"

            # Simular operación completada
            result_data = {
                "executed_price": 50001,
                "executed_quantity": 0.001,
                "fees": 0.0001,
            }

            await tracker.update_operation_status(
                operation_id, OperationStatus.COMPLETED, result_data
            )

            # Verificar que se movió al historial
            assert (
                operation_id not in tracker.active_operations
            ), "Operación completada no se movió al historial"

            # Verificar métricas actualizadas
            updated_summary = await tracker.get_operation_summary()
            assert (
                updated_summary["total_operations"] == 1
            ), "Total de operaciones no se incrementó"
            assert (
                updated_summary["successful_operations"] == 1
            ), "Operaciones exitosas no se incrementó"

            self.test_results["tests"]["operation_tracker"] = {
                "status": "PASSED",
                "details": "OperationTracker funcionando correctamente con tracking completo de operaciones",
                "total_operations": updated_summary["total_operations"],
                "successful_operations": updated_summary["successful_operations"],
                "test_operation_id": operation_id,
            }

            logger.info("✅ OperationTracker: PASSED")

        except Exception as e:
            logger.error(f"❌ OperationTracker: FAILED - {e}")
            self.test_results["tests"]["operation_tracker"] = {
                "status": "FAILED",
                "error": str(e),
            }

    async def test_integrity_monitor(self):
        """Probar IntegrityMonitor"""
        logger.info("🔍 Probando IntegrityMonitor...")

        try:
            # Crear instancia
            monitor = IntegrityMonitor()

            # Verificar inicialización
            assert monitor.monitoring_active == True, "Monitoreo no está activo"
            assert (
                monitor.check_interval == 300
            ), "Intervalo de verificación comprehensiva incorrecto"
            assert (
                monitor.critical_check_interval == 60
            ), "Intervalo de verificación crítica incorrecto"
            assert monitor.critical_threshold == 70.0, "Umbral crítico incorrecto"
            assert monitor.warning_threshold == 85.0, "Umbral de advertencia incorrecto"
            assert monitor.healthy_threshold == 95.0, "Umbral saludable incorrecto"

            # Verificar métodos disponibles
            assert hasattr(
                monitor, "start_monitoring"
            ), "Método start_monitoring no encontrado"
            assert hasattr(
                monitor, "perform_comprehensive_check"
            ), "Método perform_comprehensive_check no encontrado"
            assert hasattr(
                monitor, "get_integrity_summary"
            ), "Método get_integrity_summary no encontrado"
            assert hasattr(
                monitor, "force_integrity_check"
            ), "Método force_integrity_check no encontrado"

            # Verificar estado inicial
            summary = await monitor.get_integrity_summary()
            assert (
                "overall_integrity_score" in summary
            ), "Campo overall_integrity_score no encontrado en summary"
            assert (
                "monitoring_active" in summary
            ), "Campo monitoring_active no encontrado en summary"
            assert (
                "check_interval_seconds" in summary
            ), "Campo check_interval_seconds no encontrado en summary"

            # Verificar scores iniciales
            assert (
                monitor.overall_integrity_score == 100.0
            ), "Score de integridad inicial incorrecto"
            assert (
                monitor.balance_integrity_score == 100.0
            ), "Score de integridad de balances inicial incorrecto"
            assert (
                monitor.operation_integrity_score == 100.0
            ), "Score de integridad de operaciones inicial incorrecto"

            self.test_results["tests"]["integrity_monitor"] = {
                "status": "PASSED",
                "details": "IntegrityMonitor inicializado correctamente con todos los métodos y configuraciones requeridos",
                "overall_integrity_score": monitor.overall_integrity_score,
                "monitoring_active": monitor.monitoring_active,
                "check_interval": monitor.check_interval,
            }

            logger.info("✅ IntegrityMonitor: PASSED")

        except Exception as e:
            logger.error(f"❌ IntegrityMonitor: FAILED - {e}")
            self.test_results["tests"]["integrity_monitor"] = {
                "status": "FAILED",
                "error": str(e),
            }

    async def test_component_integration(self):
        """Probar integración entre componentes"""
        logger.info("🔍 Probando integración entre componentes...")

        try:
            # Crear instancias
            validator = BalanceValidator()
            tracker = OperationTracker()
            monitor = IntegrityMonitor()

            # Conectar componentes
            monitor.set_components(validator, tracker)

            # Verificar que la conexión se estableció
            assert (
                monitor.balance_validator is not None
            ), "BalanceValidator no se conectó al monitor"
            assert (
                monitor.operation_tracker is not None
            ), "OperationTracker no se conectó al monitor"

            # Verificar que son las mismas instancias
            assert (
                monitor.balance_validator is validator
            ), "BalanceValidator no es la misma instancia"
            assert (
                monitor.operation_tracker is tracker
            ), "OperationTracker no es la misma instancia"

            # Simular operación y verificar que se refleja en el monitor
            test_operation = {
                "asset": "ETHUSDT",
                "type": "GRID_SELL",
                "side": "SELL",
                "quantity": 0.01,
                "price": 3000,
                "user_id": "test_user",
                "strategy_id": "test_strategy",
                "grid_level": 2,
            }

            operation_id = await tracker.track_operation(test_operation)

            # Verificar que el monitor puede acceder a la información
            operation_summary = await tracker.get_operation_summary()
            assert (
                operation_summary["total_operations"] > 0
            ), "Monitor no puede acceder a información de operaciones"

            self.test_results["tests"]["component_integration"] = {
                "status": "PASSED",
                "details": "Componentes integrados correctamente y pueden comunicarse entre sí",
                "connected_components": [
                    "BalanceValidator",
                    "OperationTracker",
                    "IntegrityMonitor",
                ],
                "test_operation_id": operation_id,
            }

            logger.info("✅ Integración entre componentes: PASSED")

        except Exception as e:
            logger.error(f"❌ Integración entre componentes: FAILED - {e}")
            self.test_results["tests"]["component_integration"] = {
                "status": "FAILED",
                "error": str(e),
            }

    async def evaluate_overall_results(self):
        """Evaluar resultados generales de las pruebas"""
        logger.info("📊 Evaluando resultados generales...")

        passed_tests = 0
        failed_tests = 0

        for test_name, test_result in self.test_results["tests"].items():
            if test_result["status"] == "PASSED":
                passed_tests += 1
            else:
                failed_tests += 1

        total_tests = len(self.test_results["tests"])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        if failed_tests == 0:
            self.test_results["overall_status"] = "PASSED"
            self.test_results["summary"] = (
                f"Todas las pruebas pasaron exitosamente ({passed_tests}/{total_tests})"
            )
        elif success_rate >= 80:
            self.test_results["overall_status"] = "PARTIALLY_PASSED"
            self.test_results["summary"] = (
                f"La mayoría de las pruebas pasaron ({passed_tests}/{total_tests}, {success_rate:.1f}%)"
            )
        else:
            self.test_results["overall_status"] = "FAILED"
            self.test_results["summary"] = (
                f"Muchas pruebas fallaron ({passed_tests}/{total_tests}, {success_rate:.1f}%)"
            )

        self.test_results["passed_tests"] = passed_tests
        self.test_results["failed_tests"] = failed_tests
        self.test_results["total_tests"] = total_tests
        self.test_results["success_rate"] = success_rate

        logger.info(
            f"📊 Resultados: {passed_tests}/{total_tests} pruebas pasaron ({success_rate:.1f}%)"
        )

    async def generate_test_report(self):
        """Generar reporte de pruebas"""
        logger.info("📋 Generando reporte de pruebas...")

        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        reports_dir = os.getenv("REPORTS_DIR", "reports")
        integrity_dir = os.path.join(reports_dir, "integrity")
        try:
            os.makedirs(integrity_dir, exist_ok=True)
        except Exception:
            pass
        filename = os.path.join(
            integrity_dir, f"integrity_components_test_report_{timestamp}.json"
        )

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.test_results, f, indent=2, ensure_ascii=False)

            logger.info(f"📋 Reporte guardado en: {filename}")

            # Mostrar resumen en consola
            print("\n" + "=" * 60)
            print("📊 REPORTE DE PRUEBAS DE COMPONENTES DE INTEGRIDAD")
            print("=" * 60)
            print(f"🕐 Timestamp: {self.test_results['timestamp']}")
            print(f"📈 Estado General: {self.test_results['overall_status']}")
            print(f"📋 Resumen: {self.test_results['summary']}")
            print(f"✅ Pruebas Exitosas: {self.test_results['passed_tests']}")
            print(f"❌ Pruebas Fallidas: {self.test_results['failed_tests']}")
            print(f"📊 Tasa de Éxito: {self.test_results['success_rate']:.1f}%")
            print("\n📋 Detalles por Componente:")

            for test_name, test_result in self.test_results["tests"].items():
                status_emoji = "✅" if test_result["status"] == "PASSED" else "❌"
                print(f"  {status_emoji} {test_name}: {test_result['status']}")
                if test_result["status"] == "FAILED":
                    print(f"     Error: {test_result['error']}")

            print("=" * 60)

        except Exception as e:
            logger.error(f"❌ Error generando reporte: {e}")


async def main():
    """Función principal"""
    logger.info("🚀 Iniciando pruebas de componentes de integridad")

    tester = IntegrityComponentsTester()
    await tester.run_all_tests()

    logger.info("🏁 Pruebas completadas")


if __name__ == "__main__":
    asyncio.run(main())
