"""
B5 — breakers cross-process (API ↔ Celery) vía store compartido.

Simula dos procesos con dos instancias ``CircuitBreakers`` que comparten el
mismo ``BreakerStateStore`` (InMemory en unit; Redis en integración opcional).
Paper-safe: no toca live ni configs freeze.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.breaker_state_store import (
    BREAKER_REDIS_KEY,
    InMemoryBreakerStateStore,
    RedisBreakerStateStore,
    build_breaker_state_store,
    resolve_store_backend,
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


# ─── COV-1.2: store gaps (Redis mock, resolve, fail-soft) ───


def test_redis_store_lazy_client_via_get_redis_client(monkeypatch):
    """Sin client inyectado, _redis() usa get_redis_client (mock, sin red)."""
    fake = MagicMock()
    fake.hgetall.return_value = {}
    monkeypatch.setattr(
        "app.core.distributed_lock.get_redis_client",
        lambda: fake,
    )
    store = RedisBreakerStateStore(client=None)
    assert store.load_all() == {}
    fake.hgetall.assert_called_once_with(BREAKER_REDIS_KEY)


def test_redis_store_decode_str_fields_and_skip_non_dict():
    """Payload str (no bytes) + JSON no-dict se ignoran; corrupt → fail-soft."""
    fake = MagicMock()
    fake.hgetall.return_value = {
        "ok_breaker": json.dumps({"active": True, "reason": "paper"}),
        "bad_type": json.dumps([1, 2, 3]),
        "corrupt": "{not-json",
    }
    store = RedisBreakerStateStore(client=fake)
    loaded = store.load_all()
    assert "ok_breaker" in loaded
    assert loaded["ok_breaker"].active is True
    assert "bad_type" not in loaded
    assert "corrupt" not in loaded


def test_redis_store_clear_all_ok_and_fail_soft(monkeypatch):
    monkeypatch.setenv("GRIDBOT_ALLOW_BREAKER_STORE_WIPE", "1")
    fake = MagicMock()
    store = RedisBreakerStateStore(client=fake)
    store.clear_all()
    fake.delete.assert_called_once_with(BREAKER_REDIS_KEY)

    fake.delete.side_effect = ConnectionError("redis down")
    store.clear_all()  # no lanza


def test_resolve_store_backend_variants(monkeypatch):
    assert resolve_store_backend("memory") == "memory"
    assert resolve_store_backend("mem") == "memory"
    assert resolve_store_backend("local") == "memory"
    assert resolve_store_backend("redis") == "redis"

    monkeypatch.delenv("CB_SHARED_STORE", raising=False)
    fake = MagicMock()
    fake.ping.return_value = True
    with patch("app.core.distributed_lock.get_redis_client", return_value=fake):
        assert resolve_store_backend("auto") == "redis"

    with patch(
        "app.core.distributed_lock.get_redis_client",
        side_effect=ConnectionError("no redis"),
    ):
        assert resolve_store_backend("auto") == "memory"


def test_build_breaker_state_store_redis_with_injected_client():
    fake = MagicMock()
    store = build_breaker_state_store(backend="redis", redis_client=fake)
    assert isinstance(store, RedisBreakerStateStore)
    store.save_breaker(
        "system_integrity",
        trip_record_from_mapping({"active": True, "reason": "cov"}),
    )
    fake.hset.assert_called()


def test_build_breaker_state_store_redis_fallback_memory(monkeypatch):
    """Redis obligatorio pero connect falla → memoria (fail-soft)."""
    monkeypatch.setenv("CB_SHARED_STORE", "redis")
    with patch(
        "app.core.breaker_state_store.RedisBreakerStateStore.load_all",
        side_effect=ConnectionError("boom"),
    ):
        store = build_breaker_state_store(backend="redis", redis_client=None)
    assert isinstance(store, InMemoryBreakerStateStore)


def test_store_metric_helpers_fail_soft_when_prometheus_down():
    """_inc_sync_error / _set_backend_metric no propagan si labels explota."""
    from app.core import breaker_state_store as bss

    with patch("app.core.metrics.breaker_store_sync_errors_total") as m:
        m.labels.side_effect = RuntimeError("prom down")
        bss._inc_sync_error("read")

    with patch("app.core.metrics.breaker_store_backend") as m:
        m.labels.side_effect = RuntimeError("prom down")
        bss._set_backend_metric("memory")


@pytest.mark.asyncio
async def test_persist_and_hydrate_fail_soft():
    """Errores de store no rompen activate/hydrate (trading path)."""
    store = MagicMock()
    store.load_all.side_effect = RuntimeError("hydrate fail")
    store.save_breaker.side_effect = RuntimeError("persist fail")
    cb = CircuitBreakers(store=store)
    # hydrate falló en init; activate aún debe funcionar in-proc
    ok = await cb.activate_breaker("system_integrity", "paper persist fail")
    assert ok is True
    assert cb.is_breaker_active("system_integrity") is True


def test_apply_record_ignora_nombre_desconocido():
    store = InMemoryBreakerStateStore()
    cb = CircuitBreakers(store=store)
    record = trip_record_from_mapping({"active": True, "reason": "ghost"})
    cb._apply_record("no_existe", record)
    assert "no_existe" not in cb.breakers


def test_reset_shared_breakers_clear_all_fail_soft(monkeypatch):
    monkeypatch.setenv("CB_SHARED_STORE", "memory")
    bad = MagicMock()
    bad.clear_all.side_effect = RuntimeError("clear fail")
    bad.load_all.return_value = {}
    with patch(
        "app.core.breaker_state_store.build_breaker_state_store",
        return_value=bad,
    ):
        cb = reset_shared_breakers()
    assert isinstance(cb, CircuitBreakers)


def test_empty_hydrate_persist_closed_does_not_wipe_si_reduce_only():
    """Recreate/hydrate vacío no pisa SI OPEN+REDUCE_ONLY en el store (Ola 1 logs L0)."""
    store = InMemoryBreakerStateStore()
    seed = CircuitBreakers(store=store)
    store.save_breaker(
        "system_integrity",
        trip_record_from_mapping(
            {
                "active": True,
                "reason": "Demasiadas pérdidas consecutivas: 19",
                "operational_state": "REDUCE_ONLY",
                "activation_count": 1,
            }
        ),
    )
    hydrated = CircuitBreakers(store=store)
    assert hydrated.is_breaker_active("system_integrity") is True
    assert hydrated.breakers["system_integrity"].get("operational_state") == "REDUCE_ONLY"

    empty = CircuitBreakers(store=store)
    empty.breakers["system_integrity"]["active"] = False
    empty.breakers["system_integrity"]["reason"] = None
    empty._persist_breaker("system_integrity")

    remote = store.load_all()["system_integrity"]
    assert remote.active is True
    assert remote.operational_state == "REDUCE_ONLY"


@pytest.mark.asyncio
async def test_deactivate_still_persists_closed_si():
    """allow_close=True (deactivate) sí puede cerrar el HASH; no es recreate."""
    store = InMemoryBreakerStateStore()
    proc = CircuitBreakers(store=store)
    await proc.activate_breaker("system_integrity", "paper test")
    assert store.load_all()["system_integrity"].active is True
    assert await proc.deactivate_breaker("system_integrity") is True
    assert store.load_all()["system_integrity"].active is False
