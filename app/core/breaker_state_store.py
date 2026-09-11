"""
Store compartido de circuit breakers (API ↔ Celery).

B5: el singleton ``get_shared_breakers()`` es in-process; API y worker Celery
viven en procesos distintos. Este módulo persiste trips/open state (+ cooldown
anti-flap) en Redis HASH ``gridbot:breakers:v1``.

Fail-soft: si Redis no está disponible, se degrada a memoria local y se
registra el error (métrica + log). Paper-safe.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

BREAKER_REDIS_KEY = "gridbot:breakers:v1"
_DEFAULT_BACKEND = "auto"  # auto | redis | memory
ALLOW_BREAKER_STORE_WIPE_ENV = "GRIDBOT_ALLOW_BREAKER_STORE_WIPE"
EMPTY_STORE_POLICY_ENV = "CB_EMPTY_STORE_POLICY"
POLICY_FAIL_CLOSED = "fail_closed"
POLICY_FRESH = "fresh"


@dataclass
class BreakerTripRecord:
    """Snapshot persistible de un breaker (open state + anti-flap)."""

    active: bool = False
    activated_at: Optional[str] = None
    reason: Optional[str] = None
    last_activation_ts: float = 0.0
    last_activation_reason: str = ""
    activation_count: int = 0
    # v2: faltante en registros v1 => migración conservadora en policy.
    operational_state: Optional[str] = None
    transitioned_at: Optional[str] = None
    transition_reason: Optional[str] = None
    state_version: int = 2

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def trip_record_from_mapping(data: Dict[str, Any]) -> BreakerTripRecord:
    """Construye un record tolerante a campos faltantes / tipos sueltos."""
    return BreakerTripRecord(
        active=bool(data.get("active", False)),
        activated_at=data.get("activated_at"),
        reason=data.get("reason"),
        last_activation_ts=float(data.get("last_activation_ts") or 0.0),
        last_activation_reason=str(data.get("last_activation_reason") or ""),
        activation_count=int(data.get("activation_count") or 0),
        operational_state=data.get("operational_state"),
        transitioned_at=data.get("transitioned_at"),
        transition_reason=data.get("transition_reason"),
        state_version=int(data.get("state_version") or 1),
    )


def _inc_sync_error(op: str) -> None:
    try:
        from app.core.metrics import breaker_store_sync_errors_total

        breaker_store_sync_errors_total.labels(op=op).inc()
    except Exception:
        pass


def _set_backend_metric(backend: str) -> None:
    try:
        from app.core.metrics import breaker_store_backend

        for name in ("redis", "memory"):
            breaker_store_backend.labels(backend=name).set(1 if name == backend else 0)
    except Exception:
        pass


def redis_breaker_wipe_allowed() -> bool:
    """DEL del HASH paper/prod solo con bandera explícita (RCA 2026-08-30)."""
    raw = (os.getenv(ALLOW_BREAKER_STORE_WIPE_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def empty_store_policy() -> str:
    """Qué hacer si Redis no tiene field system_integrity.

    ``fail_closed`` (default): UNKNOWN → OPEN+REDUCE_ONLY. Incluye ambiente
    nuevo: nace bloqueado a propósito; Desk desbloquea o setea ``fresh``.
    ``fresh``: arranque genuinamente nuevo (staging / segunda instancia);
    vacío es esperado, no se alerta ni se fail-closed.
    """
    raw = (os.getenv(EMPTY_STORE_POLICY_ENV) or POLICY_FAIL_CLOSED).strip().lower()
    if raw in {POLICY_FRESH, "new", "empty_ok", "allow_empty"}:
        return POLICY_FRESH
    return POLICY_FAIL_CLOSED


class BreakerStateStore(Protocol):
    def load_all(self) -> Dict[str, BreakerTripRecord]: ...

    def save_breaker(self, name: str, record: BreakerTripRecord) -> None: ...

    def clear_all(self) -> None: ...


class InMemoryBreakerStateStore:
    """Store en proceso — útil para tests y degradación sin Redis."""

    durable = False

    def __init__(self) -> None:
        self._data: Dict[str, BreakerTripRecord] = {}

    def load_all(self) -> Dict[str, BreakerTripRecord]:
        return {
            name: BreakerTripRecord(**asdict(record))
            for name, record in self._data.items()
        }

    def save_breaker(self, name: str, record: BreakerTripRecord) -> None:
        self._data[name] = BreakerTripRecord(**asdict(record))

    def clear_all(self) -> None:
        self._data.clear()


class RedisBreakerStateStore:
    """Persistencia HASH Redis. Fail-soft en lectura/escritura."""

    durable = True

    def __init__(self, client: Any = None) -> None:
        self._client = client
        self.last_load_ok = True

    def _redis(self) -> Any:
        if self._client is not None:
            return self._client
        from app.core.distributed_lock import get_redis_client

        return get_redis_client()

    @staticmethod
    def _decode_field(raw: Any) -> str:
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)

    def load_all(self) -> Dict[str, BreakerTripRecord]:
        try:
            raw_map = self._redis().hgetall(BREAKER_REDIS_KEY) or {}
            self.last_load_ok = True
        except Exception as exc:  # noqa: BLE001 — fail-soft
            logger.warning("breaker store Redis read failed: %s", exc)
            _inc_sync_error("read")
            self.last_load_ok = False
            return {}

        result: Dict[str, BreakerTripRecord] = {}
        for field, payload in raw_map.items():
            name = self._decode_field(field)
            try:
                data = json.loads(self._decode_field(payload))
                if not isinstance(data, dict):
                    continue
                result[name] = trip_record_from_mapping(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "breaker store corrupt field %s: %s", name, exc
                )
                _inc_sync_error("decode")
        return result

    def save_breaker(self, name: str, record: BreakerTripRecord) -> None:
        try:
            self._redis().hset(BREAKER_REDIS_KEY, name, record.to_json())
        except Exception as exc:  # noqa: BLE001 — fail-soft
            logger.warning(
                "breaker store Redis write failed (%s): %s", name, exc
            )
            _inc_sync_error("write")

    def clear_all(self) -> None:
        if not redis_breaker_wipe_allowed():
            logger.error(
                "Refusing Redis DEL %s without %s=1 "
                "(RCA Docs/ops/rca-si-redis-hash-wipe-2026-08-30.md)",
                BREAKER_REDIS_KEY,
                ALLOW_BREAKER_STORE_WIPE_ENV,
            )
            _inc_sync_error("clear_denied")
            return
        try:
            self._redis().delete(BREAKER_REDIS_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("breaker store Redis clear failed: %s", exc)
            _inc_sync_error("clear")


def resolve_store_backend(explicit: Optional[str] = None) -> str:
    """Resuelve backend: memory | redis (auto intenta Redis)."""
    raw = (explicit or os.getenv("CB_SHARED_STORE") or _DEFAULT_BACKEND).strip().lower()
    if raw in {"memory", "mem", "local"}:
        return "memory"
    if raw == "redis":
        return "redis"
    # auto
    try:
        from app.core.distributed_lock import get_redis_client

        get_redis_client().ping()
        return "redis"
    except Exception:
        return "memory"


def build_breaker_state_store(
    backend: Optional[str] = None,
    *,
    redis_client: Any = None,
) -> BreakerStateStore:
    """Factory del store compartido.

    ``backend``: ``memory`` | ``redis`` | ``auto`` (default env ``CB_SHARED_STORE``).
    """
    resolved = resolve_store_backend(backend)
    if resolved == "redis":
        try:
            store = RedisBreakerStateStore(client=redis_client)
            # Validar conectividad si no inyectaron cliente
            if redis_client is None:
                store.load_all()
            _set_backend_metric("redis")
            logger.info("breaker shared store: Redis (%s)", BREAKER_REDIS_KEY)
            return store
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "breaker shared store Redis unavailable (%s); fallback memory",
                exc,
            )
            _inc_sync_error("connect")
    _set_backend_metric("memory")
    return InMemoryBreakerStateStore()
