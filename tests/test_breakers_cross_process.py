"""
B5 — breakers cross-process (API ↔ Celery) vía store compartido.

Simula dos procesos con dos instancias ``CircuitBreakers`` que comparten el
mismo ``BreakerStateStore`` (InMemory en unit; Redis en integración opcional).
Paper-safe: no toca live ni configs freeze.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.core.breaker_state_store import (
    BREAKER_REDIS_KEY,
    InMemoryBreakerStateStore,
    RedisBreakerStateStore,
    build_breaker_state_store,
    trip_record_from_mapping,
)
from app.core.circuit_breakers import CircuitBreakers, reset_shared_breakers


@pytest.fixture(autouse=True)
def _isolate_shared_breakers(monkeypatch):
    """Tests B5 no deben contaminar el singleton ni forzar Redis real."""
    monkeypatch.setenv("CB_SHARED_STORE", "memory")
    reset_shared_breakers()
    yield
    reset_shared_breakers()


@pytest.mark.asyncio
async def test_worker_trip_visible_en_api_via_store_compartido():
    """DoD B5: trip en 'worker' se ve en 'api' sin compartir instancia Python."""
    store = InMemoryBreakerStateStore()
    worker = CircuitBreakers(store=store)
    api = CircuitBreakers(store=store)

    assert api.is_breaker_active("system_integrity") is False

    ok = await worker.activate_breaker(
        "system_integrity", "desync exchange paper-test"
    )
    assert ok is True
    assert worker.is_breaker_active("system_integrity") is True
    assert api.is_breaker_active("system_integrity") is True
    assert api.is_trading_halted() is True

    status = api.get_breaker_status("system_integrity")
    assert "desync" in (status.get("reason") or "")


@pytest.mark.asyncio
async def test_api_deactivate_visible_en_worker():
    store = InMemoryBreakerStateStore()
    worker = CircuitBreakers(store=store)
    api = CircuitBreakers(store=store)

    await worker.activate_breaker("balance_discrepancy", "pérdida diaria paper")
    assert api.is_breaker_active("balance_discrepancy") is True

    assert await api.deactivate_breaker("balance_discrepancy") is True
    assert worker.is_breaker_active("balance_discrepancy") is False
    assert worker.is_trading_halted() is False


@pytest.mark.asyncio
async def test_cooldown_anti_flap_compartido_entre_procesos():
    """Cooldown/razón deben vivir en el store, no solo en memoria local."""
    store = InMemoryBreakerStateStore()
    proc_a = CircuitBreakers(store=store)
    proc_b = CircuitBreakers(store=store)
    proc_a._cooldown_seconds = 300
    proc_b._cooldown_seconds = 300

    reason = "pérdida diaria excedida: 6.00% > 5.00%"
    assert await proc_a.activate_breaker("balance_discrepancy", reason) is True
    await proc_a.deactivate_breaker("balance_discrepancy")

    # Mismo evento desde el otro proceso → anti-flap
    ok = await proc_b.activate_breaker("balance_discrepancy", reason)
    assert ok is False
    assert proc_b.is_breaker_active("balance_discrepancy") is False


def test_build_breaker_state_store_memory():
    store = build_breaker_state_store(backend="memory")
    assert isinstance(store, InMemoryBreakerStateStore)


def test_redis_store_save_and_load_roundtrip():
    """RedisBreakerStateStore habla HASH sin Redis real (cliente mock)."""
    fake = MagicMock()
    fake.hgetall.return_value = {}
    store = RedisBreakerStateStore(client=fake)

    record = trip_record_from_mapping(
        {
            "active": True,
            "activated_at": "2026-08-05T12:00:00",
            "reason": "trip test",
            "last_activation_ts": 1.5,
            "last_activation_reason": "trip test",
            "activation_count": 2,
        }
    )
    store.save_breaker("system_integrity", record)

    fake.hset.assert_called_once()
    args = fake.hset.call_args
    assert args[0][0] == BREAKER_REDIS_KEY
    assert args[0][1] == "system_integrity"
    payload = json.loads(args[0][2])
    assert payload["active"] is True
    assert payload["reason"] == "trip test"

    fake.hgetall.return_value = {
        b"system_integrity": json.dumps(payload).encode("utf-8"),
    }
    loaded = store.load_all()
    assert "system_integrity" in loaded
    assert loaded["system_integrity"].active is True
    assert loaded["system_integrity"].reason == "trip test"


def test_redis_store_fail_soft_on_read_error():
    fake = MagicMock()
    fake.hgetall.side_effect = ConnectionError("redis down")
    store = RedisBreakerStateStore(client=fake)
    assert store.load_all() == {}


def test_redis_store_fail_soft_on_write_error():
    fake = MagicMock()
    fake.hset.side_effect = ConnectionError("redis down")
    store = RedisBreakerStateStore(client=fake)
    record = trip_record_from_mapping({"active": True, "reason": "x"})
    # No debe lanzar
    store.save_breaker("system_integrity", record)


def test_circuit_breakers_sin_store_sigue_in_memory():
    """Regresión: CircuitBreakers() sin store no exige Redis."""
    cb = CircuitBreakers()
    assert cb._store is None


@pytest.mark.asyncio
async def test_hydrate_on_init_from_store():
    store = InMemoryBreakerStateStore()
    first = CircuitBreakers(store=store)
    await first.activate_breaker("critical_mode", "emergency paper")

    second = CircuitBreakers(store=store)
    assert second.is_breaker_active("critical_mode") is True
    assert second.get_activation_count("critical_mode") >= 1
