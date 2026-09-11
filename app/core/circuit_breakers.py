"""
Circuit Breakers - Módulo de Circuit Breakers Simplificado
GridBot v2.5 - Componente de Integridad Integrado

B1: ``get_shared_breakers()`` unifica instancias in-process.
B5: store opcional (Redis) comparte trips/open state entre API y Celery.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

STORE_MISSING_REASON = (
    "breaker_store_missing (fail-closed REDUCE_ONLY; HASH ausente)"
)
STORE_MISSING_CEO_CHANNEL = "am:BreakerStoreMissingFailClosed"
STORE_MISSING_CEO_FP = "BreakerStoreMissingFailClosed"


def _notify_breaker_store_missing() -> None:
    """Telegram CEO (debounce 1h). La métrica/gauge la publica hydrate."""
    try:
        from app.core.telegram_ceo_copy import (
            HOLD_PNL_MIN_REPEAT_S,
            ceo_plain_enabled,
            render_breaker_store_missing_telegram,
            should_emit_ceo,
        )
        from app.services.telegram_alert import send_telegram_alert

        if not ceo_plain_enabled():
            return
        if not should_emit_ceo(
            STORE_MISSING_CEO_CHANNEL,
            STORE_MISSING_CEO_FP,
            min_repeat_s=HOLD_PNL_MIN_REPEAT_S,
        ):
            return
        send_telegram_alert(render_breaker_store_missing_telegram())
    except Exception as exc:  # noqa: BLE001
        logger.warning("breaker_store_missing telegram skip: %s", exc)


if TYPE_CHECKING:
    from app.core.breaker_state_store import BreakerStateStore, BreakerTripRecord


def _normalize_reason(reason: Optional[str]) -> str:
    """Normaliza razón para comparar eventos (anti-flap)."""
    if reason is None:
        return ""
    return " ".join(str(reason).strip().casefold().split())


class CircuitBreakers:
    """Clase simplificada de circuit breakers para componentes de integridad"""

    def __init__(self, store: Optional["BreakerStateStore"] = None):
        self.logger = logger
        self._store = store
        self.breakers = {
            "balance_discrepancy": {
                "active": False,
                "activated_at": None,
                "reason": None,
            },
            "operation_failure_rate": {
                "active": False,
                "activated_at": None,
                "reason": None,
            },
            "system_integrity": {"active": False, "activated_at": None, "reason": None},
            "critical_mode": {"active": False, "activated_at": None, "reason": None},
        }
        from app.core.boot_log import boot_info

        boot_info(self.logger, "circuit_breakers", "🔧 Módulo de circuit breakers inicializado")
        # Cooldown por breaker y estado
        self._last_activation_ts: Dict[str, float] = {}
        self._last_activation_reason: Dict[str, str] = {}
        # Aperturas acumuladas por breaker (solo observabilidad)
        self._activation_count: Dict[str, int] = {}
        import os

        try:
            self._cooldown_seconds = int(os.getenv("CB_COOLDOWN_SECONDS", "300"))
        except Exception:
            self._cooldown_seconds = 300  # 5 minutos

        self._fail_closed_this_process = False

        if self._store is not None:
            self._hydrate_from_store()

    def _record_for(self, breaker_type: str) -> "BreakerTripRecord":
        from app.core.breaker_state_store import BreakerTripRecord

        state = self.breakers[breaker_type]
        return BreakerTripRecord(
            active=bool(state["active"]),
            activated_at=state.get("activated_at"),
            reason=state.get("reason"),
            last_activation_ts=float(self._last_activation_ts.get(breaker_type, 0.0)),
            last_activation_reason=str(
                self._last_activation_reason.get(breaker_type, "")
            ),
            activation_count=int(self._activation_count.get(breaker_type, 0)),
            operational_state=state.get("operational_state"),
            transitioned_at=state.get("transitioned_at"),
            transition_reason=state.get("transition_reason"),
        )

    def _apply_record(self, breaker_type: str, record: "BreakerTripRecord") -> None:
        if breaker_type not in self.breakers:
            return
        self.breakers[breaker_type]["active"] = bool(record.active)
        self.breakers[breaker_type]["activated_at"] = record.activated_at
        self.breakers[breaker_type]["reason"] = record.reason
        self.breakers[breaker_type]["operational_state"] = record.operational_state
        self.breakers[breaker_type]["transitioned_at"] = record.transitioned_at
        self.breakers[breaker_type]["transition_reason"] = record.transition_reason
        self._last_activation_ts[breaker_type] = float(record.last_activation_ts or 0.0)
        self._last_activation_reason[breaker_type] = str(
            record.last_activation_reason or ""
        )
        self._activation_count[breaker_type] = int(record.activation_count or 0)

    def _persist_breaker(self, breaker_type: str, *, allow_close: bool = False) -> None:
        """Persiste un breaker. No pisa un OPEN remoto con CLOSED salvo ``allow_close``.

        Recreate/hydrate de un proceso vacío no debe borrar SI REDUCE_ONLY en Redis.
        ``remote is None`` tampoco autoriza HSET closed (RCA 2026-08-30): es anomalía,
        no un close de Desk. Solo ``deactivate_breaker`` sobre un OPEN existente
        puede cerrar el HASH.
        """
        if self._store is None or breaker_type not in self.breakers:
            return
        try:
            record = self._record_for(breaker_type)
            if not record.active:
                remote = self._store.load_all().get(breaker_type)
                if remote is None:
                    self.logger.error(
                        "Anomalía persist closed '%s': field ausente "
                        "(no HSET closed sobre vacío; RCA HASH wipe 2026-08-30)",
                        breaker_type,
                    )
                    try:
                        from app.core.metrics import (
                            breaker_store_persist_anomaly_total,
                        )

                        breaker_store_persist_anomaly_total.labels(
                            kind="closed_over_missing"
                        ).inc()
                    except Exception:
                        pass
                    return
                if not allow_close and remote.active:
                    self.logger.warning(
                        "Skip persist closed '%s': store sigue OPEN "
                        "(recreate/hydrate vacío no wipe SI)",
                        breaker_type,
                    )
                    return
            self._store.save_breaker(breaker_type, record)
        except Exception as exc:  # noqa: BLE001 — never break trading path
            self.logger.warning(
                "No se pudo persistir breaker '%s' en store: %s", breaker_type, exc
            )

    def _store_is_durable(self) -> bool:
        return getattr(self._store, "durable", False) is True

    def _store_last_load_ok(self) -> bool:
        """False solo si Redis falló al leer (no confundir con HASH vacío)."""
        return getattr(self._store, "last_load_ok", True) is not False

    def _publish_store_missing_gauge(self, value: int) -> None:
        if self._fail_closed_this_process:
            value = 1
        try:
            from app.core.metrics import breaker_store_missing

            breaker_store_missing.set(float(value))
        except Exception:
            pass

    def _apply_fail_closed_si(self) -> None:
        now_iso = datetime.now().isoformat()
        now_ts = time.time()
        state = self.breakers["system_integrity"]
        state["active"] = True
        state["activated_at"] = now_iso
        state["reason"] = STORE_MISSING_REASON
        state["operational_state"] = "REDUCE_ONLY"
        state["transitioned_at"] = now_iso
        state["transition_reason"] = STORE_MISSING_REASON
        self._last_activation_ts["system_integrity"] = now_ts
        self._last_activation_reason["system_integrity"] = _normalize_reason(
            STORE_MISSING_REASON
        )
        if int(self._activation_count.get("system_integrity", 0) or 0) == 0:
            self._activation_count["system_integrity"] = 1

    def _maybe_fail_closed_missing_si(self, remote: Dict[str, Any]) -> None:
        from app.core.breaker_state_store import POLICY_FRESH, empty_store_policy

        if not self._store_is_durable():
            self._publish_store_missing_gauge(0)
            return
        if not self._store_last_load_ok():
            # Lectura Redis falló: no asumir HASH borrado ni persistir OPEN encima.
            self._publish_store_missing_gauge(0)
            return
        if "system_integrity" in remote:
            self._publish_store_missing_gauge(0)
            return
        if empty_store_policy() == POLICY_FRESH:
            self._publish_store_missing_gauge(0)
            return

        self._apply_fail_closed_si()
        first = not self._fail_closed_this_process
        self._fail_closed_this_process = True
        self._publish_store_missing_gauge(1)
        if first:
            self.logger.error(
                "HASH breakers ausente: fail-closed system_integrity REDUCE_ONLY "
                "(%s)",
                STORE_MISSING_REASON,
            )
            try:
                from app.core.metrics import (
                    breaker_state,
                    breaker_store_fail_closed_total,
                )

                breaker_store_fail_closed_total.inc()
                breaker_state.labels(type="system_integrity").set(1)
            except Exception:
                pass
            _notify_breaker_store_missing()
        self._persist_breaker("system_integrity")

    def _hydrate_from_store(self) -> None:
        if self._store is None:
            return
        try:
            remote = self._store.load_all()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("No se pudo hidratar breakers desde store: %s", exc)
            return
        for name, record in remote.items():
            self._apply_record(name, record)
        self._maybe_fail_closed_missing_si(remote)

    def _refresh_from_store(self) -> None:
        """Relee el store antes de consultas de estado (cross-process)."""
        self._hydrate_from_store()

    async def activate_breaker(
        self,
        breaker_type: str,
        reason: str = None,
        *,
        force: bool = False,
    ) -> bool:
        """Activar un circuit breaker específico.

        Contrato de cooldown (B4 — anti-flap, no anti-protección):
        - Si ya está activo: edge-trigger; retorna True sin re-loggear ni
          cambiar ``activated_at`` / razón.
        - Si está inactivo y la última apertura fue hace < cooldown:
          - Misma razón (normalizada) que el último trip → omitir (anti-flap
            del mismo evento).
          - Razón distinta → permitir (trip de pérdida / evento real distinto).
        - ``force=True`` (p. ej. modo crítico) ignora el cooldown.
        """
        try:
            if breaker_type not in self.breakers:
                self.logger.warning(
                    f"⚠️ Tipo de circuit breaker desconocido: {breaker_type}"
                )
                return False

            # Cross-process: alinear cooldown/estado antes de decidir
            self._refresh_from_store()

            # Edge-trigger: solo loggear/cambiar estado si pasa de inactivo a activo
            if not self.breakers[breaker_type]["active"]:
                now = time.time()
                last = self._last_activation_ts.get(breaker_type, 0.0)
                norm_reason = _normalize_reason(reason)
                last_reason = self._last_activation_reason.get(breaker_type, "")

                if (
                    not force
                    and self._cooldown_seconds > 0
                    and now - last < self._cooldown_seconds
                    and norm_reason == last_reason
                    and last_reason != ""
                ):
                    self.logger.warning(
                        f"⏳ Cooldown anti-flap para '{breaker_type}' "
                        f"(mismo evento), activación omitida"
                    )
                    return False

                self.breakers[breaker_type]["active"] = True
                self.breakers[breaker_type]["activated_at"] = datetime.now().isoformat()
                self.breakers[breaker_type]["reason"] = (
                    reason or "Activado automáticamente"
                )
                self._last_activation_ts[breaker_type] = now
                self._last_activation_reason[breaker_type] = (
                    norm_reason
                    or _normalize_reason(self.breakers[breaker_type]["reason"])
                )
                self.logger.warning(
                    f"🚨 Circuit breaker '{breaker_type}' activado: {reason}"
                )
                # Métrica de estado
                try:
                    from app.core.metrics import breaker_opens_total, breaker_state

                    breaker_state.labels(type=breaker_type).set(1)
                    breaker_opens_total.labels(type=breaker_type).inc()
                except Exception:
                    pass
                try:
                    self._activation_count[breaker_type] = (
                        self._activation_count.get(breaker_type, 0) + 1
                    )
                except Exception:
                    pass
                self._persist_breaker(breaker_type)
            return True

        except Exception as e:
            self.logger.error(
                f"❌ Error activando circuit breaker '{breaker_type}': {e}"
            )
            return False

    async def deactivate_breaker(self, breaker_type: str) -> bool:
        """Desactivar un circuit breaker específico"""
        try:
            if breaker_type not in self.breakers:
                self.logger.warning(
                    f"⚠️ Tipo de circuit breaker desconocido: {breaker_type}"
                )
                return False

            self._refresh_from_store()

            self.breakers[breaker_type]["active"] = False
            self.breakers[breaker_type]["activated_at"] = None
            self.breakers[breaker_type]["reason"] = None

            self.logger.info(
                "✅ Circuit breaker '%s' desactivado (reason previa ya no aplica; "
                "metric/state cleared)",
                breaker_type,
            )
            try:
                from app.core.metrics import breaker_state

                breaker_state.labels(type=breaker_type).set(0)
            except Exception:
                pass
            self._persist_breaker(breaker_type, allow_close=True)
            return True

        except Exception as e:
            self.logger.error(
                f"❌ Error desactivando circuit breaker '{breaker_type}': {e}"
            )
            return False

    async def transition_operational_state(
        self, breaker_type: str, state: str, *, reason: str
    ) -> bool:
        """Transición auditada; no desactiva el trip ni altera su antigüedad."""
        if breaker_type not in self.breakers:
            return False
        from app.core.system_integrity_state import SystemIntegrityState

        try:
            target = SystemIntegrityState(state.upper())
        except ValueError:
            return False
        self._refresh_from_store()
        current = self.breakers[breaker_type]
        if target is SystemIntegrityState.CLOSED and current.get("active"):
            return False
        current["operational_state"] = target.value
        current["transitioned_at"] = datetime.now().isoformat()
        current["transition_reason"] = reason
        self._persist_breaker(breaker_type)
        return True

    async def activate_critical_mode(self) -> bool:
        """Activar modo crítico (todos los circuit breakers).

        Usa ``force=True`` para ignorar cooldown anti-flap: es emergencia.
        """
        try:
            for breaker_type in self.breakers:
                await self.activate_breaker(
                    breaker_type, "Modo crítico activado", force=True
                )

            # Activar modo crítico especial
            self.breakers["critical_mode"]["active"] = True
            self.breakers["critical_mode"]["activated_at"] = datetime.now().isoformat()
            self.breakers["critical_mode"]["reason"] = (
                "MODO CRÍTICO - TODOS LOS CIRCUIT BREAKERS ACTIVADOS"
            )
            self._persist_breaker("critical_mode")

            self.logger.critical(
                "🚨🚨🚨 MODO CRÍTICO ACTIVADO - TODOS LOS CIRCUIT BREAKERS ACTIVADOS 🚨🚨🚨"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error activando modo crítico: {e}")
            return False

    async def deactivate_critical_mode(self) -> bool:
        """Desactivar modo crítico"""
        try:
            for breaker_type in self.breakers:
                await self.deactivate_breaker(breaker_type)

            self.logger.info(
                "✅ Modo crítico desactivado - todos los circuit breakers desactivados"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error desactivando modo crítico: {e}")
            return False

    def is_breaker_active(self, breaker_type: str) -> bool:
        """Verificar si un circuit breaker está activo"""
        self._refresh_from_store()
        if breaker_type not in self.breakers:
            return False
        return self.breakers[breaker_type]["active"]

    def is_critical_mode_active(self) -> bool:
        """Verificar si el modo crítico está activo"""
        self._refresh_from_store()
        return self.breakers["critical_mode"]["active"]

    def is_trading_halted(self) -> bool:
        """Verificar si el trading está detenido por circuit breakers"""
        self._refresh_from_store()
        # Trading está detenido si hay cualquier circuit breaker activo
        return any(status["active"] for status in self.breakers.values())

    def get_breaker_status(self, breaker_type: str) -> Dict[str, Any]:
        """Obtener estado de un circuit breaker específico"""
        self._refresh_from_store()
        if breaker_type not in self.breakers:
            return {"error": f"Tipo de circuit breaker desconocido: {breaker_type}"}

        return self.breakers[breaker_type].copy()

    def get_cooldown_seconds(self) -> int:
        """Ventana de cooldown configurada (segundos) anti-flap del mismo evento."""
        return self._cooldown_seconds

    def get_last_activation_ts(self, breaker_type: str) -> float:
        """Timestamp unix de la última apertura (0.0 si nunca se abrió)."""
        self._refresh_from_store()
        try:
            return float(self._last_activation_ts.get(breaker_type, 0.0))
        except Exception:
            return 0.0

    def get_activation_count(self, breaker_type: str) -> int:
        """Cantidad de aperturas registradas para el breaker (store-aware)."""
        self._refresh_from_store()
        try:
            return int(self._activation_count.get(breaker_type, 0))
        except Exception:
            return 0

    def get_all_breakers_status(self) -> Dict[str, Any]:
        """Obtener estado de todos los circuit breakers"""
        self._refresh_from_store()
        return {
            "critical_mode": self.breakers["critical_mode"]["active"],
            "active_breakers": [
                name for name, status in self.breakers.items() if status["active"]
            ],
            "total_active": sum(
                1 for status in self.breakers.values() if status["active"]
            ),
            "breakers": self.breakers.copy(),
        }

    def get_breaker_summary(self) -> str:
        """Obtener resumen de circuit breakers en formato texto"""
        self._refresh_from_store()
        active_count = sum(1 for status in self.breakers.values() if status["active"])
        total_count = len(self.breakers)

        summary = f"📊 CIRCUIT BREAKERS: {active_count}/{total_count} activos\n\n"

        for name, status in self.breakers.items():
            emoji = "🔴" if status["active"] else "🟢"
            status_text = "ACTIVO" if status["active"] else "INACTIVO"
            summary += f"{emoji} {name}: {status_text}\n"

            if status["active"] and status["reason"]:
                summary += f"   Razón: {status['reason']}\n"
                summary += f"   Activado: {status['activated_at']}\n"
            summary += "\n"

        return summary


_shared_breakers: "CircuitBreakers | None" = None


def get_shared_breakers() -> "CircuitBreakers":
    """Única fuente de verdad para breakers (API ↔ worker).

    B1: componentes (``AutoCircuitBreaker``, rutas ``/breakers``, tareas Celery,
    lifespan de FastAPI) deben usar esta instancia. Crear ``CircuitBreakers()``
    fresco deja el dashboard con ``any_open: false`` mientras hay trips reales
    en otra instancia in-process.

    B5: el store (Redis por defecto si ``REDIS_URL`` responde; memoria si no)
    comparte trips/open state entre procesos. Override: ``CB_SHARED_STORE``.
    """
    global _shared_breakers
    if _shared_breakers is None:
        from app.core.breaker_state_store import build_breaker_state_store

        _shared_breakers = CircuitBreakers(store=build_breaker_state_store())
    return _shared_breakers


def reset_shared_breakers() -> "CircuitBreakers":
    """Reemplaza el singleton (tests / reinicio controlado). Paper-safe.

    Limpia el store activo para no filtrar trips entre tests. El HASH Redis
    ``gridbot:breakers:v1`` **no** se borra salvo ``GRIDBOT_ALLOW_BREAKER_STORE_WIPE=1``.
    """
    global _shared_breakers
    from app.core.breaker_state_store import build_breaker_state_store

    store = build_breaker_state_store()
    try:
        store.clear_all()
    except Exception:
        pass
    _shared_breakers = CircuitBreakers(store=store)
    return _shared_breakers
