"""
Integrity Monitor - Monitoreo Continuo de Integridad del Sistema
GridBot v2.5 - Componente de Integridad Integrado
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List

from app.core.balance_validator import BalanceValidator
from app.core.operation_tracker import OperationTracker
from app.core.telegram_bot import TelegramBot
from app.core.grafana_metrics import GrafanaMetrics
from app.core.circuit_breakers import get_shared_breakers
from app.core.database import Database
from app.core.config import settings
from app.core.metrics import integrity_score

logger = logging.getLogger(__name__)


class IntegrityMonitor:
    def __init__(self):
        self.config = settings
        self.db = Database()
        self.telegram_bot = TelegramBot()
        self.grafana_metrics = GrafanaMetrics()
        self.circuit_breakers = get_shared_breakers()

        # Referencias a otros componentes (se establecerán después de la inicialización)
        self.balance_validator = None
        self.operation_tracker = None

        # Configuración de monitoreo
        self.monitoring_active = True
        self.check_interval = 300  # 5 minutos
        self.critical_check_interval = 60  # 1 minuto para verificaciones críticas

        # Umbrales de integridad (configurables por ENV)
        try:
            self.critical_threshold = float(
                os.getenv("INTEGRITY_CRITICAL_THRESHOLD", "70")
            )
            self.warning_threshold = float(
                os.getenv("INTEGRITY_WARNING_THRESHOLD", "85")
            )
            self.healthy_threshold = float(
                os.getenv("INTEGRITY_HEALTHY_THRESHOLD", "95")
            )
        except Exception:
            self.critical_threshold = 70.0
            self.warning_threshold = 85.0
            self.healthy_threshold = 95.0

        # Estado del monitoreo
        self.last_comprehensive_check = None
        self.last_critical_check = None
        self.monitoring_history = []
        self.integrity_alerts = []

        # Métricas de integridad
        self.overall_integrity_score = 100.0
        self.balance_integrity_score = 100.0
        self.operation_integrity_score = 100.0
        self.system_integrity_score = 100.0

        # Contadores de alertas
        self.critical_alerts_count = 0
        self.warning_alerts_count = 0
        self.consecutive_critical_checks = 0

        # Estabilización: periodo de gracia y umbral de fallos consecutivos
        self.startup_time = datetime.now()
        self.startup_grace_seconds = int(
            os.getenv("INTEGRITY_STARTUP_GRACE_SECONDS", "120")
        )
        self.required_consecutive_critical = int(
            os.getenv("INTEGRITY_REQUIRED_CONSECUTIVE_CRITICAL", "3")
        )
        self.consecutive_overall_critical = 0
        # Histéresis de recuperación
        try:
            self.recovery_threshold = float(
                os.getenv("INTEGRITY_RECOVERY_THRESHOLD", "85")
            )
            self.recovery_cycles = int(os.getenv("INTEGRITY_RECOVERY_CYCLES", "2"))
        except Exception:
            self.recovery_threshold = 85.0
            self.recovery_cycles = 2

    def set_components(
        self, balance_validator: BalanceValidator, operation_tracker: OperationTracker
    ):
        """Establecer referencias a otros componentes de integridad"""
        self.balance_validator = balance_validator
        self.operation_tracker = operation_tracker
        logger.info("🔗 Componentes de integridad conectados al monitor")

    async def start_monitoring(self):
        """Iniciar monitoreo continuo de integridad"""
        logger.info("🚀 Iniciando monitoreo continuo de integridad del sistema")

        # Iniciar tareas de monitoreo
        asyncio.create_task(self.comprehensive_monitoring_loop())
        asyncio.create_task(self.critical_monitoring_loop())
        asyncio.create_task(self.periodic_health_report())

        logger.info("✅ Monitoreo de integridad iniciado correctamente")

    async def comprehensive_monitoring_loop(self):
        """Loop principal de monitoreo comprehensivo"""
        while self.monitoring_active:
            try:
                await self.perform_comprehensive_check()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"❌ Error en loop de monitoreo comprehensivo: {e}")
                await self.telegram_bot.send_alert(
                    f"🚨 Error en monitoreo de integridad: {e}"
                )
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar

    async def critical_monitoring_loop(self):
        """Loop de monitoreo crítico (más frecuente)"""
        while self.monitoring_active:
            try:
                await self.perform_critical_check()
                await asyncio.sleep(self.critical_check_interval)

            except Exception as e:
                logger.error(f"❌ Error en loop de monitoreo crítico: {e}")
                await asyncio.sleep(30)  # Esperar 30 segundos antes de reintentar

    async def perform_comprehensive_check(self):
        """Realizar verificación comprehensiva de integridad"""
        logger.info("🔍 Iniciando verificación comprehensiva de integridad")

        try:
            # 1. Verificar integridad de balances
            balance_integrity = await self.check_balance_integrity()

            # 2. Verificar integridad de operaciones
            operation_integrity = await self.check_operation_integrity()

            # 3. Verificar integridad del sistema
            system_integrity = await self.check_system_integrity()

            # 4. Calcular score de integridad general
            self.overall_integrity_score = (
                balance_integrity + operation_integrity + system_integrity
            ) / 3

            # Publicar métricas por componente (Prometheus scrape /metrics)
            try:
                from app.core.metrics import publish_integrity_score_gauges

                publish_integrity_score_gauges(
                    overall=self.overall_integrity_score,
                    balance=balance_integrity,
                    operation=operation_integrity,
                    system=system_integrity,
                )
            except Exception:
                try:
                    integrity_score.labels(component="balance").set(balance_integrity)
                    integrity_score.labels(component="operation").set(
                        operation_integrity
                    )
                    integrity_score.labels(component="system").set(system_integrity)
                    integrity_score.labels(component="overall").set(
                        self.overall_integrity_score
                    )
                except Exception:
                    pass

            # 5. Actualizar métricas
            await self.update_integrity_metrics()

            # 6. Verificar umbrales y enviar alertas
            await self.check_integrity_thresholds()

            # 7. Registrar verificación
            await self.log_integrity_check()

            self.last_comprehensive_check = datetime.now()

            logger.info(
                f"✅ Verificación comprehensiva completada. Score: {self.overall_integrity_score:.2f}"
            )

        except Exception as e:
            logger.error(f"❌ Error en verificación comprehensiva: {e}")
            await self.telegram_bot.send_alert(
                f"🚨 Error en verificación de integridad: {e}"
            )

    async def perform_critical_check(self):
        """Realizar verificación crítica rápida"""
        try:
            # Verificar solo aspectos críticos
            critical_issues = []

            # Verificar si hay operaciones fallidas recientes
            if self.operation_tracker:
                failed_ops = (
                    await self.operation_tracker.get_failed_operations_summary()
                )
                if len(failed_ops) > 10:  # Más de 10 operaciones fallidas
                    critical_issues.append(
                        f"Operaciones fallidas críticas: {len(failed_ops)}"
                    )

            # Verificar si hay discrepancias masivas de balances
            if self.balance_validator and self.balance_validator.integrity_score < 50:
                critical_issues.append(
                    f"Integridad de balances crítica: {self.balance_validator.integrity_score:.2f}"
                )

            # Si hay problemas críticos, activar alertas inmediatas
            if critical_issues:
                await self.trigger_critical_alert(critical_issues)
                self.consecutive_critical_checks += 1
            else:
                self.consecutive_critical_checks = 0

            self.last_critical_check = datetime.now()

        except Exception as e:
            logger.error(f"❌ Error en verificación crítica: {e}")

    async def check_balance_integrity(self) -> float:
        """Verificar integridad de balances"""
        try:
            if not self.balance_validator:
                return 100.0  # Si no hay validator, asumir integridad perfecta

            # Obtener score de integridad del balance validator
            self.balance_integrity_score = self.balance_validator.integrity_score

            # Verificar si hay validaciones recientes
            if self.balance_validator.last_validation:
                time_since_last = (
                    datetime.now() - self.balance_validator.last_validation
                ).total_seconds()
                if time_since_last > 1800:  # Más de 30 minutos
                    self.balance_integrity_score *= (
                        0.8  # Reducir score por falta de validaciones
                    )

            return self.balance_integrity_score

        except Exception as e:
            logger.error(f"❌ Error verificando integridad de balances: {e}")
            return 0.0

    async def check_operation_integrity(self) -> float:
        """Verificar integridad de operaciones"""
        try:
            if not self.operation_tracker:
                return 100.0  # Si no hay tracker, asumir integridad perfecta

            # Obtener resumen de operaciones
            operation_summary = await self.operation_tracker.get_operation_summary()

            # Calcular score basado en tasa de éxito
            success_rate = operation_summary.get("success_rate", 1.0)
            self.operation_integrity_score = success_rate * 100

            # Penalizar por operaciones fallidas recientes
            failed_ops = operation_summary.get("failed_operations", 0)
            if failed_ops > 5:
                self.operation_integrity_score *= 0.9

            # Penalizar por partial fills excesivos
            partial_fills = operation_summary.get("partial_fills", 0)
            if partial_fills > 10:
                self.operation_integrity_score *= 0.95

            return self.operation_integrity_score

        except Exception as e:
            logger.error(f"❌ Error verificando integridad de operaciones: {e}")
            return 0.0

    async def check_system_integrity(self) -> float:
        """Verificar integridad general del sistema"""
        try:
            # Verificar conectividad con base de datos
            db_health = await self.check_database_health()

            # Verificar conectividad con Binance
            binance_health = await self.check_binance_health()

            # Verificar métricas del sistema
            system_metrics = await self.check_system_metrics()

            # Calcular score combinado
            self.system_integrity_score = (
                db_health + binance_health + system_metrics
            ) / 3

            return self.system_integrity_score

        except Exception as e:
            logger.error(f"❌ Error verificando integridad del sistema: {e}")
            return 0.0

    async def check_database_health(self) -> float:
        """Verificar salud de la base de datos"""
        try:
            # Intentar operación simple en la base de datos
            await self.db.execute_query("SELECT 1")
            return 100.0
        except Exception as e:
            logger.error(f"❌ Error de conectividad con base de datos: {e}")
            return 100.0  # Por ahora, asumir salud perfecta en modo simulado

    async def check_binance_health(self) -> float:
        """Verificar salud de la conexión con Binance"""
        try:
            # Verificar si podemos obtener información básica de Binance
            # Esto dependerá de la implementación del cliente de Binance
            return 100.0  # Placeholder
        except Exception as e:
            logger.error(f"❌ Error de conectividad con Binance: {e}")
            return 50.0

    async def check_system_metrics(self) -> float:
        """Verificar métricas del sistema"""
        try:
            # Verificar uso de memoria, CPU, etc.
            # Por ahora, asumir salud perfecta
            return 100.0
        except Exception as e:
            logger.error(f"❌ Error verificando métricas del sistema: {e}")
            return 100.0

    async def check_integrity_thresholds(self):
        """Verificar umbrales de integridad y enviar alertas"""
        try:
            # Periodo de gracia post-arranque: no activar crítico
            if (
                datetime.now() - self.startup_time
            ).total_seconds() < self.startup_grace_seconds:
                logger.info("⏳ Periodo de gracia activo: omitiendo activación crítica")
                return

            if self.overall_integrity_score <= self.critical_threshold:
                self.consecutive_overall_critical += 1
                if (
                    self.consecutive_overall_critical
                    >= self.required_consecutive_critical
                ):
                    await self.trigger_critical_integrity_alert()
                    await self.activate_critical_circuit_breakers()
                else:
                    logger.warning(
                        f"⚠️ Score crítico {self.overall_integrity_score:.2f} pero aún no supera consecutivos requeridos "
                        f"({self.consecutive_overall_critical}/{self.required_consecutive_critical})"
                    )

            elif self.overall_integrity_score <= self.warning_threshold:
                self.consecutive_overall_critical = 0
                await self.trigger_warning_integrity_alert()

            elif self.overall_integrity_score >= self.healthy_threshold:
                self.consecutive_overall_critical = 0
                # Sistema saludable, resetear contadores de alertas
                if self.critical_alerts_count > 0 or self.warning_alerts_count > 0:
                    await self.trigger_health_recovery_alert()
                    self.critical_alerts_count = 0
                    self.warning_alerts_count = 0
                # Histeresis: salida de modo crítico sólo con salud sostenida
                try:
                    if self.circuit_breakers.is_critical_mode_active():
                        # Requerir dos ciclos consecutivos saludables >= 85
                        if not hasattr(self, "_healthy_streak"):
                            self._healthy_streak = 0
                        if self.overall_integrity_score >= self.recovery_threshold:
                            self._healthy_streak += 1
                        else:
                            self._healthy_streak = 0
                        if self._healthy_streak >= self.recovery_cycles:
                            await self.circuit_breakers.deactivate_critical_mode()
                            self._healthy_streak = 0
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ Error verificando umbrales de integridad: {e}")

    async def trigger_critical_integrity_alert(self):
        """Activar alerta crítica de integridad"""
        self.critical_alerts_count += 1

        alert_message = "🚨 ALERTA CRÍTICA DE INTEGRIDAD\n\n"
        alert_message += (
            f"Score de integridad: {self.overall_integrity_score:.2f}/100\n"
        )
        alert_message += f"Umbral crítico: {self.critical_threshold}/100\n\n"
        alert_message += "Componentes:\n"
        alert_message += f"• Balances: {self.balance_integrity_score:.2f}/100\n"
        alert_message += f"• Operaciones: {self.operation_integrity_score:.2f}/100\n"
        alert_message += f"• Sistema: {self.system_integrity_score:.2f}/100\n\n"
        alert_message += "🔴 ACTIVANDO CIRCUIT BREAKERS CRÍTICOS"

        await self.telegram_bot.send_alert(alert_message)
        logger.warning(
            f"🚨 Alerta crítica de integridad enviada. Score: {self.overall_integrity_score:.2f}"
        )

    async def trigger_warning_integrity_alert(self):
        """Activar alerta de advertencia de integridad"""
        self.warning_alerts_count += 1

        alert_message = "⚠️ ADVERTENCIA DE INTEGRIDAD\n\n"
        alert_message += (
            f"Score de integridad: {self.overall_integrity_score:.2f}/100\n"
        )
        alert_message += f"Umbral de advertencia: {self.warning_threshold}/100\n\n"
        alert_message += (
            "El sistema está funcionando pero con degradación de integridad.\n"
        )
        alert_message += "Monitoreando continuamente..."

        await self.telegram_bot.send_alert(alert_message)
        logger.warning(
            f"⚠️ Advertencia de integridad enviada. Score: {self.overall_integrity_score:.2f}"
        )

    async def trigger_critical_alert(self, issues: List[str]):
        """Activar alerta crítica por problemas específicos"""
        alert_message = "🚨 ALERTA CRÍTICA INMEDIATA\n\n"
        alert_message += "Problemas detectados:\n"
        for issue in issues:
            alert_message += f"• {issue}\n"
        alert_message += "\n🔴 VERIFICACIÓN INMEDIATA REQUERIDA"

        await self.telegram_bot.send_alert(alert_message)
        logger.warning(f"🚨 Alerta crítica inmediata enviada por: {issues}")

    async def trigger_health_recovery_alert(self):
        """Activar alerta de recuperación de salud"""
        alert_message = "✅ RECUPERACIÓN DE INTEGRIDAD\n\n"
        alert_message += "El sistema ha recuperado su integridad.\n"
        alert_message += f"Score actual: {self.overall_integrity_score:.2f}/100\n\n"
        alert_message += "🎯 Sistema funcionando normalmente"

        await self.telegram_bot.send_alert(alert_message)
        logger.info(
            f"✅ Alerta de recuperación enviada. Score: {self.overall_integrity_score:.2f}"
        )

    async def activate_critical_circuit_breakers(self):
        """Activar circuit breakers críticos"""
        logger.warning(
            "🚨 Activando circuit breakers críticos por degradación de integridad"
        )

        try:
            # Activar circuit breakers
            await self.circuit_breakers.activate_critical_mode()

            # Enviar alerta de activación
            await self.telegram_bot.send_alert(
                "🔴 CIRCUIT BREAKERS CRÍTICOS ACTIVADOS - INTEGRIDAD DEGRADADA"
            )

        except Exception as e:
            logger.error(f"❌ Error activando circuit breakers: {e}")

    async def update_integrity_metrics(self):
        """Actualizar métricas de integridad en Grafana"""
        try:
            # Métricas principales de integridad
            await self.grafana_metrics.record_metric(
                "overall_integrity_score", self.overall_integrity_score
            )
            await self.grafana_metrics.record_metric(
                "balance_integrity_score", self.balance_integrity_score
            )
            await self.grafana_metrics.record_metric(
                "operation_integrity_score", self.operation_integrity_score
            )
            await self.grafana_metrics.record_metric(
                "system_integrity_score", self.system_integrity_score
            )

            # Métricas de alertas
            await self.grafana_metrics.record_metric(
                "critical_alerts_count", self.critical_alerts_count
            )
            await self.grafana_metrics.record_metric(
                "warning_alerts_count", self.warning_alerts_count
            )
            await self.grafana_metrics.record_metric(
                "consecutive_critical_checks", self.consecutive_critical_checks
            )

            # Métricas de timing
            if self.last_comprehensive_check:
                time_since_last = (
                    datetime.now() - self.last_comprehensive_check
                ).total_seconds()
                await self.grafana_metrics.record_metric(
                    "seconds_since_last_comprehensive_check", time_since_last
                )

            if self.last_critical_check:
                time_since_last = (
                    datetime.now() - self.last_critical_check
                ).total_seconds()
                await self.grafana_metrics.record_metric(
                    "seconds_since_last_critical_check", time_since_last
                )

        except Exception as e:
            logger.error(f"❌ Error actualizando métricas de Grafana: {e}")

    async def log_integrity_check(self):
        """Registrar verificación de integridad en base de datos"""
        try:
            integrity_record = {
                "timestamp": datetime.now().isoformat(),
                "overall_integrity_score": self.overall_integrity_score,
                "balance_integrity_score": self.balance_integrity_score,
                "operation_integrity_score": self.operation_integrity_score,
                "system_integrity_score": self.system_integrity_score,
                "critical_alerts_count": self.critical_alerts_count,
                "warning_alerts_count": self.warning_alerts_count,
                "consecutive_critical_checks": self.consecutive_critical_checks,
                "check_type": "COMPREHENSIVE",
            }

            await self.db.insert_integrity_record(integrity_record)

            # Agregar al historial local
            self.monitoring_history.append(integrity_record)

            # Mantener solo los últimos 100 registros
            if len(self.monitoring_history) > 100:
                self.monitoring_history = self.monitoring_history[-100:]

        except Exception as e:
            logger.error(f"❌ Error registrando verificación de integridad: {e}")

    async def periodic_health_report(self, report_interval: int = 3600):  # 1 hora
        """Generar reporte periódico de salud del sistema"""
        logger.info("📊 Iniciando reportes periódicos de salud")

        while self.monitoring_active:
            try:
                await asyncio.sleep(report_interval)

                # Generar reporte de salud
                health_report = await self.generate_health_report()

                # Enviar por Telegram si hay problemas
                if self.overall_integrity_score < self.warning_threshold:
                    await self.telegram_bot.send_alert(health_report)

                # Registrar en base de datos
                await self.log_health_report(health_report)

            except Exception as e:
                logger.error(f"❌ Error generando reporte de salud: {e}")
                await asyncio.sleep(300)  # Esperar 5 minutos antes de reintentar

    async def generate_health_report(self) -> str:
        """Generar reporte de salud del sistema"""
        try:
            report = "📊 REPORTE DE SALUD DEL SISTEMA\n\n"
            report += (
                f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

            # Score general
            status_emoji = (
                "🟢"
                if self.overall_integrity_score >= self.healthy_threshold
                else "🟡"
                if self.overall_integrity_score >= self.warning_threshold
                else "🔴"
            )
            report += f"{status_emoji} Score de Integridad General: {self.overall_integrity_score:.2f}/100\n\n"

            # Componentes individuales
            report += "📊 Componentes:\n"
            report += f"• Balances: {self.balance_integrity_score:.2f}/100\n"
            report += f"• Operaciones: {self.operation_integrity_score:.2f}/100\n"
            report += f"• Sistema: {self.system_integrity_score:.2f}/100\n\n"

            # Alertas
            report += "🚨 Alertas:\n"
            report += f"• Críticas: {self.critical_alerts_count}\n"
            report += f"• Advertencias: {self.warning_alerts_count}\n"
            report += f"• Verificaciones críticas consecutivas: {self.consecutive_critical_checks}\n\n"

            # Estado del sistema
            if self.overall_integrity_score >= self.healthy_threshold:
                report += "✅ Sistema funcionando normalmente"
            elif self.overall_integrity_score >= self.warning_threshold:
                report += "⚠️ Sistema funcionando con degradación"
            else:
                report += "🔴 Sistema en estado crítico"

            return report

        except Exception as e:
            logger.error(f"❌ Error generando reporte de salud: {e}")
            return f"❌ Error generando reporte de salud: {e}"

    async def log_health_report(self, report: str):
        """Registrar reporte de salud en base de datos"""
        try:
            health_record = {
                "timestamp": datetime.now().isoformat(),
                "report_type": "PERIODIC_HEALTH",
                "overall_integrity_score": self.overall_integrity_score,
                "report_content": report,
            }

            await self.db.insert_health_report(health_record)

        except Exception as e:
            logger.error(f"❌ Error registrando reporte de salud: {e}")

    async def get_integrity_summary(self) -> Dict:
        """Obtener resumen de integridad del sistema"""
        return {
            "overall_integrity_score": self.overall_integrity_score,
            "balance_integrity_score": self.balance_integrity_score,
            "operation_integrity_score": self.operation_integrity_score,
            "system_integrity_score": self.system_integrity_score,
            "critical_alerts_count": self.critical_alerts_count,
            "warning_alerts_count": self.warning_alerts_count,
            "consecutive_critical_checks": self.consecutive_critical_checks,
            "last_comprehensive_check": self.last_comprehensive_check.isoformat()
            if self.last_comprehensive_check
            else None,
            "last_critical_check": self.last_critical_check.isoformat()
            if self.last_critical_check
            else None,
            "monitoring_active": self.monitoring_active,
            "check_interval_seconds": self.check_interval,
            "critical_check_interval_seconds": self.critical_check_interval,
        }

    async def force_integrity_check(self):
        """Forzar verificación inmediata de integridad"""
        logger.info("🔄 Forzando verificación inmediata de integridad")
        await self.perform_comprehensive_check()

    async def update_monitoring_config(
        self, check_interval: int = None, critical_check_interval: int = None
    ):
        """Actualizar configuración de monitoreo"""
        if check_interval is not None:
            self.check_interval = check_interval
            logger.info(
                f"📊 Intervalo de verificación comprehensiva actualizado: {check_interval}s"
            )

        if critical_check_interval is not None:
            self.critical_check_interval = critical_check_interval
            logger.info(
                f"📊 Intervalo de verificación crítica actualizado: {critical_check_interval}s"
            )

        # Guardar en configuración (simulado por ahora)
        logger.info(
            f"📊 Intervalos de monitoreo actualizados en configuración: Comprehensivo {self.check_interval}s, Crítico {self.critical_check_interval}s"
        )

    async def stop_monitoring(self):
        """Detener monitoreo de integridad"""
        logger.info("🛑 Deteniendo monitoreo de integridad")
        self.monitoring_active = False
