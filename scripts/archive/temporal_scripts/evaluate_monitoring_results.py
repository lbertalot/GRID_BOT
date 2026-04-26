#!/usr/bin/env python3
"""
Script de Evaluación Comprehensiva de Resultados del Monitoreo
Analiza todos los archivos de monitoreo generados para evaluar el estado del sistema
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


class MonitoringResultsEvaluator:
    def __init__(self):
        self.monitoring_dir = "monitoring_data"
        self.paper_trading_file = "paper_trading_state.json"

    def get_all_monitoring_files(self):
        """Obtener todos los archivos de monitoreo ordenados por fecha"""
        try:
            if Path(self.monitoring_dir).exists():
                monitoring_files = list(
                    Path(self.monitoring_dir).glob("monitoring_summary_*.json")
                )
                monitoring_files.sort(key=lambda x: x.stat().st_mtime)

                all_data = []
                for file in monitoring_files:
                    with open(file, "r") as f:
                        data = json.load(f)
                        all_data.append(data)

                return all_data
            else:
                return []
        except Exception as e:
            logger.error("❌ Error obteniendo archivos de monitoreo: %s", e)
            return []

    def get_current_paper_trading_state(self):
        """Obtener estado actual del paper trading"""
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
            logger.error("❌ Error obteniendo estado del paper trading: %s", e)
            return {"structure_valid": False, "error": str(e)}

    def analyze_monitoring_consistency(self, monitoring_data):
        """Analizar consistencia del monitoreo"""
        if not monitoring_data:
            return {}

        # Análisis de estabilidad
        stability_scores = [
            data["stability_score"]["total_score"] for data in monitoring_data
        ]
        readiness_statuses = [data["readiness"]["status"] for data in monitoring_data]
        balances = [data["paper_trading"]["balance"] for data in monitoring_data]
        trade_counts = [
            data["paper_trading"]["total_trades"] for data in monitoring_data
        ]

        # Verificar consistencia
        stability_consistent = len(set(stability_scores)) == 1
        readiness_consistent = len(set(readiness_statuses)) == 1
        balance_consistent = len(set(balances)) == 1
        trades_consistent = len(set(trade_counts)) == 1

        return {
            "stability_consistent": stability_consistent,
            "readiness_consistent": readiness_consistent,
            "balance_consistent": balance_consistent,
            "trades_consistent": trades_consistent,
            "stability_scores": stability_scores,
            "readiness_statuses": readiness_statuses,
            "balances": balances,
            "trade_counts": trade_counts,
        }

    def calculate_monitoring_statistics(self, monitoring_data):
        """Calcular estadísticas del monitoreo"""
        if not monitoring_data:
            return {}

        # Estadísticas básicas
        total_checks = len(monitoring_data)
        start_time = datetime.fromisoformat(monitoring_data[0]["timestamp"])
        end_time = datetime.fromisoformat(monitoring_data[-1]["timestamp"])
        duration = end_time - start_time

        # Estadísticas de estabilidad
        stability_scores = [
            data["stability_score"]["total_score"] for data in monitoring_data
        ]
        avg_stability = sum(stability_scores) / len(stability_scores)
        min_stability = min(stability_scores)
        max_stability = max(stability_scores)

        # Estadísticas de balance
        balances = [data["paper_trading"]["balance"] for data in monitoring_data]
        avg_balance = sum(balances) / len(balances)
        min_balance = min(balances)
        max_balance = max(balances)

        return {
            "total_checks": total_checks,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "avg_stability": avg_stability,
            "min_stability": min_stability,
            "max_stability": max_stability,
            "avg_balance": avg_balance,
            "min_balance": min_balance,
            "max_balance": max_balance,
        }

    def evaluate_system_performance(self, monitoring_data):
        """Evaluar rendimiento del sistema"""
        if not monitoring_data:
            return {}

        # Evaluar estabilidad
        stability_scores = [
            data["stability_score"]["total_score"] for data in monitoring_data
        ]
        consistent_80 = all(score == 80 for score in stability_scores)

        # Evaluar readiness
        readiness_statuses = [data["readiness"]["status"] for data in monitoring_data]
        all_ready = all(status == "READY" for status in readiness_statuses)

        # Evaluar seguridad
        safety_statuses = [
            data["safety_status"]["system_safe"] for data in monitoring_data
        ]
        all_safe = all(safe for safe in safety_statuses)

        # Evaluar circuit breakers
        circuit_breaker_statuses = [
            data["safety_status"]["circuit_breaker"]["is_open"]
            for data in monitoring_data
        ]
        all_closed = all(not open for open in circuit_breaker_statuses)

        return {
            "stability_performance": {
                "consistent_80": consistent_80,
                "score": "EXCELENTE"
                if consistent_80
                else "BUENO"
                if min(stability_scores) >= 70
                else "INSUFICIENTE",
            },
            "readiness_performance": {
                "all_ready": all_ready,
                "score": "EXCELENTE"
                if all_ready
                else "BUENO"
                if "READY" in readiness_statuses
                else "INSUFICIENTE",
            },
            "safety_performance": {
                "all_safe": all_safe,
                "score": "EXCELENTE" if all_safe else "INSUFICIENTE",
            },
            "circuit_breaker_performance": {
                "all_closed": all_closed,
                "score": "EXCELENTE" if all_closed else "INSUFICIENTE",
            },
        }

    def generate_comprehensive_evaluation(self):
        """Generar evaluación comprehensiva del monitoreo"""
        print("📊 EVALUACIÓN COMPREHENSIVA DE RESULTADOS DEL MONITOREO")
        print("=" * 80)
        print(f"📅 Fecha de evaluación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🔍 Análisis Completo del Sistema de Monitoreo")
        print()

        # 1. Obtener datos del monitoreo
        print("🔍 1. RECOPILACIÓN DE DATOS DEL MONITOREO")
        print("-" * 50)
        monitoring_data = self.get_all_monitoring_files()
        if monitoring_data:
            print(f"   ✅ Archivos de monitoreo encontrados: {len(monitoring_data)}")
            print(
                f"   📅 Rango temporal: {datetime.fromisoformat(monitoring_data[0]['timestamp']).strftime('%Y-%m-%d %H:%M')} - {datetime.fromisoformat(monitoring_data[-1]['timestamp']).strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            print("   ❌ No se encontraron archivos de monitoreo")
            return
        print()

        # 2. Estado actual del paper trading
        print("📊 2. ESTADO ACTUAL DEL PAPER TRADING")
        print("-" * 50)
        paper_state = self.get_current_paper_trading_state()
        if paper_state["structure_valid"]:
            print("   ✅ Estructura del archivo válida")
            print(f"   Balance inicial: ${paper_state['initial_balance']:.2f}")
            print(f"   Balance actual: ${paper_state['balance']:.2f}")
            print(f"   Cambio: {paper_state['balance_change_pct']:.2f}%")
            print(f"   Total trades: {paper_state['total_trades']}")
        else:
            print("   ❌ Estructura del archivo inválida")
            print(f"   Error: {paper_state.get('error', 'Desconocido')}")
        print()

        # 3. Análisis de consistencia
        print("🔄 3. ANÁLISIS DE CONSISTENCIA DEL MONITOREO")
        print("-" * 50)
        consistency = self.analyze_monitoring_consistency(monitoring_data)
        if consistency:
            print(
                f"   Estabilidad consistente: {'✅ SÍ' if consistency['stability_consistent'] else '❌ NO'}"
            )
            print(
                f"   Readiness consistente: {'✅ SÍ' if consistency['readiness_consistent'] else '❌ NO'}"
            )
            print(
                f"   Balance consistente: {'✅ SÍ' if consistency['balance_consistent'] else '❌ NO'}"
            )
            print(
                f"   Trades consistentes: {'✅ SÍ' if consistency['trades_consistent'] else '❌ NO'}"
            )

            if consistency["stability_consistent"]:
                print(
                    f"   🎯 Estabilidad constante: {consistency['stability_scores'][0]}/100"
                )
            if consistency["readiness_consistent"]:
                print(
                    f"   🚀 Readiness constante: {consistency['readiness_statuses'][0]}"
                )
        print()

        # 4. Estadísticas del monitoreo
        print("📈 4. ESTADÍSTICAS DEL MONITOREO")
        print("-" * 50)
        stats = self.calculate_monitoring_statistics(monitoring_data)
        if stats:
            print(f"   📊 Total de checks: {stats['total_checks']}")
            print(f"   ⏰ Duración total: {stats['duration']}")
            print(f"   🎯 Estabilidad promedio: {stats['avg_stability']:.1f}/100")
            print(f"   🎯 Estabilidad mínima: {stats['min_stability']}/100")
            print(f"   🎯 Estabilidad máxima: {stats['max_stability']}/100")
            print(f"   💰 Balance promedio: ${stats['avg_balance']:.2f}")
            print(f"   💰 Balance mínimo: ${stats['min_balance']:.2f}")
            print(f"   💰 Balance máximo: ${stats['max_balance']:.2f}")
        print()

        # 5. Evaluación de rendimiento
        print("🏆 5. EVALUACIÓN DE RENDIMIENTO DEL SISTEMA")
        print("-" * 50)
        performance = self.evaluate_system_performance(monitoring_data)
        if performance:
            print(f"   🎯 Estabilidad: {performance['stability_performance']['score']}")
            print(f"   🚀 Readiness: {performance['readiness_performance']['score']}")
            print(f"   🛡️ Seguridad: {performance['safety_performance']['score']}")
            print(
                f"   ⚡ Circuit Breakers: {performance['circuit_breaker_performance']['score']}"
            )
        print()

        # 6. Resumen ejecutivo
        print("=" * 80)
        print("📊 RESUMEN EJECUTIVO DE LA EVALUACIÓN")
        print("=" * 80)

        if monitoring_data and paper_state["structure_valid"]:
            latest = monitoring_data[-1]
            stability_score = latest["stability_score"]["total_score"]
            readiness = latest["readiness"]["status"]

            print("✅ RESULTADOS DEL MONITOREO:")
            print(f"   • Checks ejecutados: {len(monitoring_data)}")
            print(f"   • Estabilidad final: {stability_score}/100")
            print(f"   • Readiness final: {readiness}")
            print(f"   • Balance final: ${latest['paper_trading']['balance']:.2f}")
            print(f"   • Total trades: {latest['paper_trading']['total_trades']}")

            # Evaluación general
            if (
                consistency["stability_consistent"]
                and consistency["readiness_consistent"]
            ):
                print()
                print("🎉 EVALUACIÓN GENERAL: EXCELENTE")
                print("✅ Sistema completamente estable durante todo el monitoreo")
                print("✅ Readiness consistente en READY")
                print("✅ Monitoreo funcionando perfectamente")
                print("🚀 Sistema listo para trading real")

            elif stability_score >= 80 and readiness == "READY":
                print()
                print("🟡 EVALUACIÓN GENERAL: BUENA")
                print("✅ Sistema estable al final del monitoreo")
                print("✅ Readiness en READY")
                print("⚠️ Algunas inconsistencias durante el monitoreo")
                print("📊 Requiere monitoreo adicional para validación")

            else:
                print()
                print("🔴 EVALUACIÓN GENERAL: INSUFICIENTE")
                print("❌ Sistema no alcanzó estabilidad requerida")
                print("❌ Readiness no en READY")
                print("⚠️ Requiere estabilización antes de trading real")

        else:
            print("❌ NO HAY DATOS SUFICIENTES PARA EVALUAR")
            print("⚠️ Verificar estado del monitoreo y paper trading")

        print()
        print("📋 RECOMENDACIONES:")
        if consistency["stability_consistent"] and consistency["readiness_consistent"]:
            print("   ✅ Sistema completamente validado")
            print("   🚀 Proceder con trading real")
            print("   📊 Continuar monitoreo en producción")
        elif stability_score >= 80 and readiness == "READY":
            print("   📊 Continuar monitoreo para validación completa")
            print("   🔄 Ejecutar estabilización adicional si es necesario")
            print("   ⏳ Esperar confirmación de estabilidad sostenible")
        else:
            print("   🔄 Ejecutar estabilización del sistema")
            print("   📊 Reiniciar monitoreo después de estabilización")
            print("   ⚠️ No proceder con trading real hasta estabilización")

        print()
        print("🎉 EVALUACIÓN COMPREHENSIVA COMPLETADA")
        print("📊 Estado del sistema analizado completamente")
        print("📋 Recomendaciones generadas según resultados")
        print("⏰ Seguir recomendaciones para próximos pasos")

        return {
            "monitoring_data": monitoring_data,
            "paper_state": paper_state,
            "consistency": consistency,
            "statistics": stats,
            "performance": performance,
        }


def main():
    """Función principal"""
    evaluator = MonitoringResultsEvaluator()
    result = evaluator.generate_comprehensive_evaluation()
    return result


if __name__ == "__main__":
    main()
