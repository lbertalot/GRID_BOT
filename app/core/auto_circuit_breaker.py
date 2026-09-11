"""
Auto Circuit Breaker - Activación automática basada en métricas de pérdida
GridBot v2.5 - Sistema de protección automática
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.trade import Trade
from app.core.circuit_breakers import CircuitBreakers, get_shared_breakers
from app.core.capital_risk import daily_loss_limit_fraction

logger = logging.getLogger(__name__)


def _aware_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def paper_trial_started_at() -> Optional[datetime]:
    """t0 de la prueba SI. Vacío / inválido → trial inactivo (trip duro = 5)."""
    raw = (os.getenv("PAPER_TRIAL_STARTED_AT") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("PAPER_TRIAL_STARTED_AT inválido: %s", raw)
        return None
    return _aware_dt(parsed)


def consecutive_loss_trip_threshold() -> int:
    """Umbral duro de system_integrity. WARN Telegram no sustituye esto.

    Trial paper: ``PAPER_TRIAL_STREAK_THRESHOLD`` solo si hay ``PAPER_TRIAL_STARTED_AT``.
    Sin trial el trip sigue en 5 sobre la racha SoT completa.
    """
    if paper_trial_started_at() is None:
        return 5
    raw = (os.getenv("PAPER_TRIAL_STREAK_THRESHOLD") or "").strip()
    if not raw:
        return 5
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def _is_after_watermark(closed_at: datetime, since: datetime) -> bool:
    """``closed_at > since``. Si t0 no trae microsegundos, compara al segundo.

    Env ``PAPER_TRIAL_STARTED_AT=…15:45:37+00:00`` no debe dejar pasar el close
    SoT ``…15:45:37.370240`` (mismo segundo = watermark, no ciclo nuevo).
    """
    if since.microsecond == 0:
        return closed_at.replace(microsecond=0) > since
    return closed_at > since


def consecutive_losses_from_closed_cycles(cycles, since: Optional[datetime] = None) -> int:
    """Racha de net_pnl < 0 desde el cierre más reciente. Paper SoT (L0).

    ``since``: ignora closes con ``closed_at <= since`` (watermark de prueba SI).
    """
    since_dt = _aware_dt(since)
    closed = [
        c
        for c in cycles
        if getattr(c, "state", None) == "closed" and getattr(c, "closed_at", None)
    ]
    if since_dt is not None:
        filtered = []
        for cycle in closed:
            closed_at = _aware_dt(cycle.closed_at)
            if closed_at is not None and _is_after_watermark(closed_at, since_dt):
                filtered.append(cycle)
        closed = filtered
    closed.sort(key=lambda c: c.closed_at, reverse=True)
    n = 0
    for cycle in closed:
        pnl = cycle.net_pnl_usdt
        if pnl is None:
            break
        if pnl < 0:
            n += 1
            continue
        break
    return n


def paper_window_loss_metrics(
    cycles,
    *,
    now: datetime,
    initial_cash,
) -> Dict[str, float]:
    """Pérdidas de *esta* ventana paper (ciclos cerrados), no la tabla Trade.

    Baseline = initial_cash del ledger (L0-A E0=1000). Vacío → 0. Decimal hasta el float del dict legado.
    """
    from decimal import Decimal

    baseline = Decimal(str(initial_cash))
    if baseline <= 0:
        baseline = Decimal("1")
    closed = [
        c
        for c in cycles
        if getattr(c, "state", None) == "closed"
        and getattr(c, "closed_at", None)
        and getattr(c, "net_pnl_usdt", None) is not None
        and c.net_pnl_usdt < 0
    ]

    def _sum_since(since: Optional[datetime]):
        total = Decimal("0")
        for cycle in closed:
            closed_at = cycle.closed_at
            if closed_at.tzinfo is None and since is not None and since.tzinfo is not None:
                closed_at = closed_at.replace(tzinfo=since.tzinfo)
            if since is not None and closed_at < since:
                continue
            total += Decimal(str(cycle.net_pnl_usdt))
        return total

    total_loss = _sum_since(None)
    daily_loss = _sum_since(now - timedelta(days=1))
    hourly_loss = _sum_since(now - timedelta(hours=1))
    closed_any = [
        c
        for c in cycles
        if getattr(c, "state", None) == "closed" and getattr(c, "closed_at", None)
    ]
    last_closed_at = None
    if closed_any:
        last_ts = max(c.closed_at for c in closed_any)
        last_closed_at = last_ts.isoformat() if hasattr(last_ts, "isoformat") else str(last_ts)
    return {
        "total_loss_pct": float(abs(total_loss) / baseline),
        "daily_loss_pct": float(abs(daily_loss) / baseline),
        "hourly_loss_pct": float(abs(hourly_loss) / baseline),
        "total_loss_usd": float(abs(total_loss)),
        "daily_loss_usd": float(abs(daily_loss)),
        "hourly_loss_usd": float(abs(hourly_loss)),
        "last_closed_at": last_closed_at,
    }


def format_daily_metrics_log(metrics: Dict[str, Any]) -> str:
    """Copy ops: Diario=0 no es inconsistente con Total si no hay closes hoy."""
    daily = float(metrics.get("daily_loss_pct") or 0.0)
    total = float(metrics.get("total_loss_pct") or 0.0)
    last = metrics.get("last_closed_at") or "n/a"
    if daily == 0.0:
        daily_part = f"Diario=0.00% (sin closes hoy; last={last})"
    else:
        daily_part = f"Diario={daily:.2%}"
    return f"📊 Métricas: Total={total:.2%}, {daily_part}"


class AutoCircuitBreaker:
    """
    Sistema de activación automática de circuit breakers basado en métricas de pérdida
    """

    def __init__(self, breakers: Optional[CircuitBreakers] = None):
        # B1: override solo para tests; en prod siempre get_shared_breakers().
        self._breakers_override = breakers
        self.logger = logger

        # Umbrales de activación. max_daily_loss_pct deriva del SoT ADR-003 (B3).
        self.thresholds = {
            "max_daily_loss_pct": float(daily_loss_limit_fraction()),
            "max_total_loss_pct": 0.10,  # 10% pérdida total máxima
            "max_consecutive_losses": 5,  # 5 pérdidas consecutivas máximo
            "max_hourly_loss_pct": 0.03,  # 3% pérdida por hora máxima
            "critical_loss_pct": 0.20,  # 20% pérdida crítica (modo crítico)
        }

        from app.core.boot_log import boot_info

        boot_info(self.logger, "auto_circuit_breaker", "🛡️ Auto Circuit Breaker inicializado")

    @property
    def breakers(self) -> CircuitBreakers:
        """Fuente de verdad compartida (B1); no instancia privada."""
        if self._breakers_override is not None:
            return self._breakers_override
        return get_shared_breakers()

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
                self.logger.warning(format_daily_metrics_log(loss_metrics))

            return activation_results

        except Exception as e:
            self.logger.error(f"❌ Error en auto circuit breaker: {e}")
            return {"error": str(e)}

    async def _calculate_loss_metrics(self, db: Session) -> Dict[str, float]:
        """Calcular métricas de pérdida desde la base de datos"""
        try:
            try:
                from app.core.paper_equity_ledger import (
                    paper_equity_is_source_of_truth,
                    reload_paper_ledger_from_disk,
                )

                if paper_equity_is_source_of_truth():
                    ledger = reload_paper_ledger_from_disk()
                    return paper_window_loss_metrics(
                        ledger.closed_cycles(),
                        now=datetime.now(timezone.utc),
                        initial_cash=ledger.initial_cash,
                    )
            except Exception as paper_exc:
                self.logger.debug("loss metrics paper SoT skip: %s", paper_exc)

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
                "last_closed_at": None,
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
                "last_closed_at": None,
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
            consecutive_losses = None
            latest_closed_at = None
            loss_source = "trade_db"
            try:
                from app.core.paper_equity_ledger import (
                    paper_equity_is_source_of_truth,
                    reload_paper_ledger_from_disk,
                )

                if paper_equity_is_source_of_truth():
                    # Cross-process: releer JSON (otro worker Celery pudo haber
                    # cerrado ciclos desde el último get_paper_ledger() local).
                    closed = reload_paper_ledger_from_disk().closed_cycles()
                    trial_since = paper_trial_started_at()
                    consecutive_losses = consecutive_losses_from_closed_cycles(
                        closed, since=trial_since
                    )
                    loss_source = "paper_ledger"
                    closed_ats = [c.closed_at for c in closed if c.closed_at]
                    if closed_ats:
                        latest_closed_at = max(closed_ats)
            except Exception as paper_exc:
                self.logger.debug(
                    "consecutive losses paper SoT skip: %s", paper_exc
                )

            if consecutive_losses is None:
                recent_trades = (
                    db.query(Trade)
                    .filter(Trade.profit_loss.isnot(None))
                    .order_by(Trade.timestamp.desc())
                    .limit(10)
                    .all()
                )

                consecutive_losses = 0
                loss_source = "trade_db"
                for trade in recent_trades:
                    if trade.profit_loss < 0:
                        consecutive_losses += 1
                    else:
                        break

            threshold = consecutive_loss_trip_threshold()
            trial_since = paper_trial_started_at()
            self.logger.info(
                "system_integrity check: consecutive_losses=%s threshold=%s "
                "latest_closed_at=%s source=%s trial_since=%s",
                consecutive_losses,
                threshold,
                latest_closed_at.isoformat() if latest_closed_at else None,
                loss_source,
                trial_since.isoformat() if trial_since else None,
            )

            override_result = None
            try:
                from app.core.breaker_override import check_and_consume_override

                override_result = check_and_consume_override(
                    "system_integrity",
                    ledger_latest_closed_at=latest_closed_at,
                )
            except Exception as override_exc:  # noqa: BLE001 — fail-soft a la lógica normal
                self.logger.debug(
                    "breaker_override check skip: %s", override_exc
                )

            if override_result is not None and override_result.force_reduce_only:
                reason = (
                    "Override de prueba SI expiró sin close post-t0 "
                    f"(latest_closed_at={latest_closed_at.isoformat() if latest_closed_at else 'n/a'}); "
                    "system_integrity REDUCE_ONLY (NO-GO prueba)"
                )
                await self.breakers.activate_breaker("system_integrity", reason)
                results["breakers_activated"].append("system_integrity")
                results["reasons"].append(reason)
                return

            if consecutive_losses < threshold:
                # Racha rota con datos *frescos* (post-t0 en trial). No limpiar el
                # override si aún no hay close nuevo: el idle timer debe seguir.
                latest_aware = _aware_dt(latest_closed_at)
                has_fresh_close = trial_since is None or (
                    latest_aware is not None
                    and _is_after_watermark(latest_aware, trial_since)
                )
                if has_fresh_close:
                    try:
                        from app.core.breaker_override import (
                            clear_override,
                            get_override,
                        )

                        if get_override("system_integrity") is not None:
                            clear_override("system_integrity")
                            self.logger.info(
                                "🔓 Override RCA para 'system_integrity' liberado: racha de pérdidas ya en %s (< umbral)",
                                consecutive_losses,
                            )
                    except Exception:  # noqa: BLE001 — nunca romper el path de trading
                        pass
                return

            reason = (
                f"Demasiadas pérdidas consecutivas: {consecutive_losses} "
                f"(threshold={threshold}, metric=max_consecutive_losses, "
                f"latest_closed_at={latest_closed_at.isoformat() if latest_closed_at else 'n/a'})"
            )

            skip_activation = bool(
                override_result is not None and override_result.skip_activation
            )
            if skip_activation:
                self.logger.warning(
                    "system_integrity OPEN deferred: %s (override RCA activo)",
                    reason,
                )
                results["reasons"].append(f"{reason} (override RCA activo, sin reactivar)")
                return

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
