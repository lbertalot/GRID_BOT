"""
Auto Circuit Breaker - Activación automática basada en métricas de pérdida
GridBot v2.5 - Sistema de protección automática
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.trade import Trade
from app.core.circuit_breakers import CircuitBreakers

logger = logging.getLogger(__name__)


class AutoCircuitBreaker:
    """
    Sistema de activación automática de circuit breakers basado en métricas de pérdida
    """

    def __init__(self):
        self.breakers = CircuitBreakers()
        self.logger = logger

        # Umbrales de activación (configurables)
        self.thresholds = {
            "max_daily_loss_pct": 0.05,  # 5% pérdida diaria máxima
            "max_total_loss_pct": 0.10,  # 10% pérdida total máxima
            "max_consecutive_losses": 5,  # 5 pérdidas consecutivas máximo
            "max_hourly_loss_pct": 0.03,  # 3% pérdida por hora máxima
            "critical_loss_pct": 0.20,  # 20% pérdida crítica (modo crítico)
        }

        self.logger.info("🛡️ Auto Circuit Breaker inicializado")

    async def check_and_activate_breakers(self) -> Dict[str, Any]:
        """
        Verifica métricas de pérdida y activa circuit breakers si es necesario

        Returns:
            Dict con el estado de activación y razones
        """
        try:
            db = SessionLocal()
            activation_results = {
                "breakers_activated": [],
                "reasons": [],
                "critical_mode": False,
                "total_loss_pct": 0.0,
                "daily_loss_pct": 0.0,
            }

            # Calcular métricas de pérdida
            loss_metrics = await self._calculate_loss_metrics(db)
            activation_results.update(loss_metrics)

            # Verificar umbrales y activar breakers
            await self._check_daily_loss_threshold(loss_metrics, activation_results)
            await self._check_total_loss_threshold(loss_metrics, activation_results)
            await self._check_consecutive_losses(db, activation_results)
            await self._check_hourly_loss_threshold(loss_metrics, activation_results)
            await self._check_critical_loss_threshold(loss_metrics, activation_results)

            db.close()

            # Log de activaciones
            if activation_results["breakers_activated"]:
                self.logger.warning(
                    f"🚨 Circuit breakers activados: {activation_results['breakers_activated']}"
                )
                self.logger.warning(
                    f"📊 Métricas: Total={loss_metrics['total_loss_pct']:.2%}, Diario={loss_metrics['daily_loss_pct']:.2%}"
                )

            return activation_results

        except Exception as e:
            self.logger.error(f"❌ Error en auto circuit breaker: {e}")
            return {"error": str(e)}

    async def _calculate_loss_metrics(self, db: Session) -> Dict[str, float]:
        """Calcular métricas de pérdida desde la base de datos"""
        try:
            # Obtener baseline del portafolio
            baseline_value = 347.93  # Valor inicial del análisis

            # Calcular pérdida total
            total_loss = (
                db.query(func.sum(Trade.profit_loss))
                .filter(Trade.profit_loss.isnot(None), Trade.profit_loss < 0)
                .scalar()
                or 0.0
            )

            total_loss_pct = (
                abs(total_loss) / baseline_value if baseline_value > 0 else 0.0
            )

            # Calcular pérdida diaria (últimas 24 horas)
            yesterday = datetime.now() - timedelta(days=1)
            daily_loss = (
                db.query(func.sum(Trade.profit_loss))
                .filter(
                    Trade.profit_loss.isnot(None),
                    Trade.profit_loss < 0,
                    Trade.timestamp >= yesterday,
                )
                .scalar()
                or 0.0
            )

            daily_loss_pct = (
                abs(daily_loss) / baseline_value if baseline_value > 0 else 0.0
            )

            # Calcular pérdida por hora (última hora)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            hourly_loss = (
                db.query(func.sum(Trade.profit_loss))
                .filter(
                    Trade.profit_loss.isnot(None),
                    Trade.profit_loss < 0,
                    Trade.timestamp >= one_hour_ago,
                )
                .scalar()
                or 0.0
            )

            hourly_loss_pct = (
                abs(hourly_loss) / baseline_value if baseline_value > 0 else 0.0
            )

            return {
                "total_loss_pct": total_loss_pct,
                "daily_loss_pct": daily_loss_pct,
                "hourly_loss_pct": hourly_loss_pct,
                "total_loss_usd": abs(total_loss),
                "daily_loss_usd": abs(daily_loss),
                "hourly_loss_usd": abs(hourly_loss),
            }

        except Exception as e:
            self.logger.error(f"Error calculando métricas de pérdida: {e}")
            return {
                "total_loss_pct": 0.0,
                "daily_loss_pct": 0.0,
                "hourly_loss_pct": 0.0,
                "total_loss_usd": 0.0,
                "daily_loss_usd": 0.0,
                "hourly_loss_usd": 0.0,
            }

    async def _check_daily_loss_threshold(
        self, metrics: Dict[str, float], results: Dict[str, Any]
    ):
        """Verificar umbral de pérdida diaria"""
        if metrics["daily_loss_pct"] > self.thresholds["max_daily_loss_pct"]:
            reason = f"Pérdida diaria excedida: {metrics['daily_loss_pct']:.2%} > {self.thresholds['max_daily_loss_pct']:.2%}"
            await self.breakers.activate_breaker("balance_discrepancy", reason)
            results["breakers_activated"].append("balance_discrepancy")
            results["reasons"].append(reason)

    async def _check_total_loss_threshold(
        self, metrics: Dict[str, float], results: Dict[str, Any]
    ):
        """Verificar umbral de pérdida total"""
        if metrics["total_loss_pct"] > self.thresholds["max_total_loss_pct"]:
            reason = f"Pérdida total excedida: {metrics['total_loss_pct']:.2%} > {self.thresholds['max_total_loss_pct']:.2%}"
            await self.breakers.activate_breaker("operation_failure_rate", reason)
            results["breakers_activated"].append("operation_failure_rate")
            results["reasons"].append(reason)

    async def _check_consecutive_losses(self, db: Session, results: Dict[str, Any]):
        """Verificar pérdidas consecutivas"""
        try:
            # Obtener últimos trades ordenados por timestamp
            recent_trades = (
                db.query(Trade)
                .filter(Trade.profit_loss.isnot(None))
                .order_by(Trade.timestamp.desc())
                .limit(10)
                .all()
            )

            consecutive_losses = 0
            for trade in recent_trades:
                if trade.profit_loss < 0:
                    consecutive_losses += 1
                else:
                    break

            if consecutive_losses >= self.thresholds["max_consecutive_losses"]:
                reason = f"Demasiadas pérdidas consecutivas: {consecutive_losses}"
                await self.breakers.activate_breaker("system_integrity", reason)
                results["breakers_activated"].append("system_integrity")
                results["reasons"].append(reason)

        except Exception as e:
            self.logger.error(f"Error verificando pérdidas consecutivas: {e}")

    async def _check_hourly_loss_threshold(
        self, metrics: Dict[str, float], results: Dict[str, Any]
    ):
        """Verificar umbral de pérdida por hora"""
        if metrics["hourly_loss_pct"] > self.thresholds["max_hourly_loss_pct"]:
            reason = f"Pérdida por hora excedida: {metrics['hourly_loss_pct']:.2%} > {self.thresholds['max_hourly_loss_pct']:.2%}"
            await self.breakers.activate_breaker("operation_failure_rate", reason)
            if "operation_failure_rate" not in results["breakers_activated"]:
                results["breakers_activated"].append("operation_failure_rate")
            results["reasons"].append(reason)

    async def _check_critical_loss_threshold(
        self, metrics: Dict[str, float], results: Dict[str, Any]
    ):
        """Verificar umbral de pérdida crítica (modo crítico)"""
        if metrics["total_loss_pct"] > self.thresholds["critical_loss_pct"]:
            reason = f"PÉRDIDA CRÍTICA DETECTADA: {metrics['total_loss_pct']:.2%} > {self.thresholds['critical_loss_pct']:.2%}"
            await self.breakers.activate_critical_mode()
            results["critical_mode"] = True
            results["breakers_activated"].append("critical_mode")
            results["reasons"].append(reason)
            self.logger.critical(f"🚨🚨🚨 MODO CRÍTICO ACTIVADO: {reason} 🚨🚨🚨")

    async def get_breakers_status(self) -> Dict[str, Any]:
        """Obtener estado actual de todos los circuit breakers"""
        return self.breakers.get_all_breakers_status()

    async def manual_activation(self, breaker_type: str, reason: str) -> bool:
        """Activación manual de circuit breakers"""
        try:
            result = await self.breakers.activate_breaker(breaker_type, reason)
            if result:
                self.logger.warning(
                    f"🔧 Circuit breaker '{breaker_type}' activado manualmente: {reason}"
                )
            return result
        except Exception as e:
            self.logger.error(f"Error en activación manual: {e}")
            return False

    async def manual_deactivation(self, breaker_type: str) -> bool:
        """Desactivación manual de circuit breakers"""
        try:
            result = await self.breakers.deactivate_breaker(breaker_type)
            if result:
                self.logger.info(
                    f"✅ Circuit breaker '{breaker_type}' desactivado manualmente"
                )
            return result
        except Exception as e:
            self.logger.error(f"Error en desactivación manual: {e}")
            return False


# Instancia global para uso en el sistema
auto_circuit_breaker = AutoCircuitBreaker()
