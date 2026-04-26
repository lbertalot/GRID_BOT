#!/usr/bin/env python3
"""
Sistema de Monitoreo Continuo para Reactivación
GridBot V2.5 - Fase 6
"""

import logging
import json
import os
import time
from datetime import datetime
from typing import Dict
import threading

logger = logging.getLogger(__name__)


class ContinuousMonitoring:
    """
    Sistema de monitoreo continuo durante reactivación
    """

    def __init__(self):
        self.monitoring_active = False
        self.monitoring_thread = None
        self.monitoring_interval = 30  # segundos
        self.monitoring_file = "continuous_monitoring.json"
        self.start_time = None
        self.monitoring_data = {
            "start_time": None,
            "last_check": None,
            "total_checks": 0,
            "alerts_triggered": 0,
            "circuit_breaker_activations": 0,
            "paper_trading_trades": 0,
            "real_trading_trades": 0,
            "balance_changes": [],
            "performance_metrics": [],
            "status_history": [],
        }
        self.load_monitoring_data()

    def load_monitoring_data(self):
        """Carga datos de monitoreo previos"""
        try:
            if os.path.exists(self.monitoring_file):
                with open(self.monitoring_file, "r") as f:
                    data = json.load(f)
                    self.monitoring_data.update(data)
                logger.info("✅ Datos de monitoreo continuo cargados")
        except Exception as e:
            logger.error(f"Error cargando datos de monitoreo: {e}")

    def save_monitoring_data(self):
        """Guarda datos de monitoreo"""
        try:
            self.monitoring_data["last_check"] = datetime.now().isoformat()
            with open(self.monitoring_file, "w") as f:
                json.dump(self.monitoring_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando datos de monitoreo: {e}")

    def start_monitoring(self):
        """Inicia el monitoreo continuo"""
        if self.monitoring_active:
            logger.warning("⚠️ Monitoreo ya está activo")
            return False

        try:
            self.monitoring_active = True
            self.start_time = datetime.now()
            self.monitoring_data["start_time"] = self.start_time.isoformat()

            # Iniciar thread de monitoreo
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop, daemon=True
            )
            self.monitoring_thread.start()

            logger.info("✅ Monitoreo continuo iniciado")
            return True

        except Exception as e:
            logger.error(f"Error iniciando monitoreo: {e}")
            self.monitoring_active = False
            return False

    def stop_monitoring(self):
        """Detiene el monitoreo continuo"""
        if not self.monitoring_active:
            logger.warning("⚠️ Monitoreo no está activo")
            return

        try:
            self.monitoring_active = False

            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)

            self.save_monitoring_data()
            logger.info("✅ Monitoreo continuo detenido")

        except Exception as e:
            logger.error(f"Error deteniendo monitoreo: {e}")

    def _monitoring_loop(self):
        """Loop principal de monitoreo"""
        logger.info("🔄 Iniciando loop de monitoreo continuo")

        while self.monitoring_active:
            try:
                # Ejecutar verificación
                self._perform_monitoring_check()

                # Esperar intervalo
                time.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Error en loop de monitoreo: {e}")
                time.sleep(self.monitoring_interval)

    def _perform_monitoring_check(self):
        """Ejecuta una verificación de monitoreo"""
        try:
            check_time = datetime.now()
            self.monitoring_data["total_checks"] += 1

            # 1. Verificar circuit breaker
            circuit_breaker_status = self._check_circuit_breaker()

            # 2. Verificar estado del sistema
            system_status = self._check_system_status()

            # 3. Verificar paper trading
            paper_trading_status = self._check_paper_trading()

            # 4. Verificar configuración
            config_status = self._check_configuration()

            # 5. Verificar métricas de rendimiento
            performance_status = self._check_performance()

            # 6. Registrar estado
            status_record = {
                "timestamp": check_time.isoformat(),
                "circuit_breaker": circuit_breaker_status,
                "system_status": system_status,
                "paper_trading": paper_trading_status,
                "configuration": config_status,
                "performance": performance_status,
            }

            self.monitoring_data["status_history"].append(status_record)

            # Mantener solo los últimos 100 registros
            if len(self.monitoring_data["status_history"]) > 100:
                self.monitoring_data["status_history"] = self.monitoring_data[
                    "status_history"
                ][-100:]

            # 7. Verificar alertas
            self._check_alerts(status_record)

            # 8. Guardar datos
            self.save_monitoring_data()

            logger.debug(
                f"✅ Verificación de monitoreo completada: {check_time.strftime('%H:%M:%S')}"
            )

        except Exception as e:
            logger.error(f"Error en verificación de monitoreo: {e}")

    def _check_circuit_breaker(self) -> Dict:
        """Verifica estado del circuit breaker"""
        try:
            from app.core.circuit_breaker import circuit_breaker

            status = circuit_breaker.get_status()

            if status["is_open"]:
                self.monitoring_data["circuit_breaker_activations"] += 1
                logger.warning(f"🚨 Circuit breaker activado: {status['reason']}")

            return {
                "is_open": status["is_open"],
                "reason": status.get("reason"),
                "daily_loss": status["current_state"]["daily_loss"],
                "total_loss": status["current_state"]["total_loss"],
                "consecutive_losses": status["current_state"]["consecutive_losses"],
            }

        except Exception as e:
            logger.error(f"Error verificando circuit breaker: {e}")
            return {"error": str(e)}

    def _check_system_status(self) -> Dict:
        """Verifica estado general del sistema"""
        try:
            from app.core.safety_validator import get_system_safety_status

            safety_status = get_system_safety_status()

            return {
                "system_safe": safety_status["system_safe"],
                "overall_status": safety_status.get("overall_status", "UNKNOWN"),
            }

        except Exception as e:
            logger.error(f"Error verificando estado del sistema: {e}")
            return {"error": str(e)}

    def _check_paper_trading(self) -> Dict:
        """Verifica estado del paper trading"""
        try:
            from app.core.paper_trading import get_paper_portfolio_summary

            portfolio = get_paper_portfolio_summary()

            # Contar trades
            if portfolio["total_trades"] > self.monitoring_data["paper_trading_trades"]:
                new_trades = (
                    portfolio["total_trades"]
                    - self.monitoring_data["paper_trading_trades"]
                )
                self.monitoring_data["paper_trading_trades"] = portfolio["total_trades"]
                logger.info(f"📊 Nuevos trades de paper trading: {new_trades}")

            return {
                "balance": portfolio["current_balance"],
                "total_trades": portfolio["total_trades"],
                "open_positions": portfolio["open_positions"],
                "total_pnl": portfolio["total_pnl"],
                "total_pnl_pct": portfolio["total_pnl_pct"],
            }

        except Exception as e:
            logger.error(f"Error verificando paper trading: {e}")
            return {"error": str(e)}

    def _check_configuration(self) -> Dict:
        """Verifica configuración del sistema"""
        try:
            from app.core.unified_config import get_config

            config = get_config()
            summary = config.get_config_summary()

            return {
                "trading_enabled": summary["system_settings"]["trading_enabled"],
                "paper_trading": summary["system_settings"]["paper_trading"],
                "emergency_stop": summary["system_settings"]["emergency_stop_enabled"],
                "total_assets": summary["assets_summary"]["total_assets"],
                "active_assets": summary["assets_summary"]["active_assets"],
            }

        except Exception as e:
            logger.error(f"Error verificando configuración: {e}")
            return {"error": str(e)}

    def _check_performance(self) -> Dict:
        """Verifica métricas de rendimiento"""
        try:
            from app.core.monitoring import get_monitoring_status

            monitoring_status = get_monitoring_status()

            # Calcular métricas de rendimiento
            if self.start_time:
                uptime = datetime.now() - self.start_time
                uptime_hours = uptime.total_seconds() / 3600

                # Calcular trades por hora
                total_trades = (
                    self.monitoring_data["paper_trading_trades"]
                    + self.monitoring_data["real_trading_trades"]
                )
                trades_per_hour = total_trades / uptime_hours if uptime_hours > 0 else 0

                performance_metrics = {
                    "uptime_hours": round(uptime_hours, 2),
                    "trades_per_hour": round(trades_per_hour, 2),
                    "total_checks": self.monitoring_data["total_checks"],
                    "system_status": monitoring_status["system_status"],
                }

                self.monitoring_data["performance_metrics"].append(performance_metrics)

                # Mantener solo los últimos 50 registros
                if len(self.monitoring_data["performance_metrics"]) > 50:
                    self.monitoring_data["performance_metrics"] = self.monitoring_data[
                        "performance_metrics"
                    ][-50:]

                return performance_metrics

            return {"error": "Start time not set"}

        except Exception as e:
            logger.error(f"Error verificando rendimiento: {e}")
            return {"error": str(e)}

    def _check_alerts(self, status_record: Dict):
        """Verifica y genera alertas"""
        try:
            alerts = []

            # Alerta 1: Circuit breaker activado
            if status_record["circuit_breaker"]["is_open"]:
                alerts.append(
                    {
                        "level": "CRITICAL",
                        "message": f"Circuit breaker activado: {status_record['circuit_breaker']['reason']}",
                        "timestamp": status_record["timestamp"],
                        "category": "SAFETY",
                    }
                )

            # Alerta 2: Sistema no seguro
            if not status_record["system_status"]["system_safe"]:
                alerts.append(
                    {
                        "level": "WARNING",
                        "message": "Sistema no está en estado seguro",
                        "timestamp": status_record["timestamp"],
                        "category": "SAFETY",
                    }
                )

            # Alerta 3: Trading real habilitado durante reactivación
            if status_record["configuration"]["trading_enabled"]:
                alerts.append(
                    {
                        "level": "WARNING",
                        "message": "Trading real habilitado durante reactivación",
                        "timestamp": status_record["timestamp"],
                        "category": "CONFIGURATION",
                    }
                )

            # Alerta 4: Pérdidas significativas en paper trading
            paper_trading = status_record["paper_trading"]
            if "total_pnl_pct" in paper_trading and paper_trading["total_pnl_pct"] < -5:
                alerts.append(
                    {
                        "level": "WARNING",
                        "message": f"Pérdidas significativas en paper trading: {paper_trading['total_pnl_pct']:.2f}%",
                        "timestamp": status_record["timestamp"],
                        "category": "PERFORMANCE",
                    }
                )

            # Registrar alertas
            if alerts:
                self.monitoring_data["alerts_triggered"] += len(alerts)

                for alert in alerts:
                    logger.warning(f"🚨 ALERTA: {alert['message']}")

                    # Aquí se podrían enviar notificaciones por email/SMS
                    # self._send_alert(alert)

        except Exception as e:
            logger.error(f"Error verificando alertas: {e}")

    def get_monitoring_summary(self) -> Dict:
        """Obtiene resumen del monitoreo"""
        if not self.start_time:
            return {"error": "Monitoreo no iniciado"}

        uptime = datetime.now() - self.start_time
        uptime_hours = uptime.total_seconds() / 3600

        return {
            "monitoring_active": self.monitoring_active,
            "start_time": self.start_time.isoformat(),
            "uptime_hours": round(uptime_hours, 2),
            "total_checks": self.monitoring_data["total_checks"],
            "alerts_triggered": self.monitoring_data["alerts_triggered"],
            "circuit_breaker_activations": self.monitoring_data[
                "circuit_breaker_activations"
            ],
            "paper_trading_trades": self.monitoring_data["paper_trading_trades"],
            "real_trading_trades": self.monitoring_data["real_trading_trades"],
            "last_check": self.monitoring_data["last_check"],
            "recent_status": self.monitoring_data["status_history"][-5:]
            if self.monitoring_data["status_history"]
            else [],
        }

    def get_detailed_report(self) -> Dict:
        """Obtiene reporte detallado del monitoreo"""
        return {
            "summary": self.get_monitoring_summary(),
            "status_history": self.monitoring_data["status_history"],
            "performance_metrics": self.monitoring_data["performance_metrics"],
            "monitoring_data": self.monitoring_data,
        }


# Instancia global del monitoreo continuo
continuous_monitoring = ContinuousMonitoring()


def start_continuous_monitoring() -> bool:
    """Función de conveniencia para iniciar monitoreo"""
    return continuous_monitoring.start_monitoring()


def stop_continuous_monitoring():
    """Función de conveniencia para detener monitoreo"""
    continuous_monitoring.stop_monitoring()


def get_monitoring_summary() -> Dict:
    """Función de conveniencia para obtener resumen"""
    return continuous_monitoring.get_monitoring_summary()


def get_detailed_report() -> Dict:
    """Función de conveniencia para obtener reporte detallado"""
    return continuous_monitoring.get_detailed_report()
