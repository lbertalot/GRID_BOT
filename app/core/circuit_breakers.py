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
        Solo ``deactivate_breaker`` (allow_close=True) puede cerrar el HASH.
        """
        if self._store is None or breaker_type not in self.breakers:
            return
        try:
            record = self._record_for(breaker_type)
            if not record.active and not allow_close:
                remote = self._store.load_all().get(breaker_type)
                if remote is not None and remote.active:
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

    Limpia el store activo para no filtrar trips entre tests.
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
