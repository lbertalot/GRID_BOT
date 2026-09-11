"""C→B→A: wipe Redis, persist-on-empty, hydrate fail-closed.

Paper-only. PROMOTE_LIVE: NO.
RCA: Docs/ops/rca-si-redis-hash-wipe-2026-08-30.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.breaker_state_store import (
    ALLOW_BREAKER_STORE_WIPE_ENV,
    BREAKER_REDIS_KEY,
    EMPTY_STORE_POLICY_ENV,
    InMemoryBreakerStateStore,
    RedisBreakerStateStore,
    redis_breaker_wipe_allowed,
    trip_record_from_mapping,
)
from app.core.circuit_breakers import (
    STORE_MISSING_REASON,
    CircuitBreakers,
    reset_shared_breakers,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CB_SHARED_STORE", "memory")
    monkeypatch.delenv(ALLOW_BREAKER_STORE_WIPE_ENV, raising=False)
    monkeypatch.delenv(EMPTY_STORE_POLICY_ENV, raising=False)
    reset_shared_breakers()
    yield
    reset_shared_breakers()


def _redis_store(hgetall=None) -> tuple[RedisBreakerStateStore, MagicMock]:
    fake = MagicMock()
    fake.hgetall.return_value = {} if hgetall is None else hgetall
    return RedisBreakerStateStore(client=fake), fake


# --- C: clear_all no toca Redis paper sin bandera ---


def test_redis_wipe_denied_without_flag():
    assert redis_breaker_wipe_allowed() is False
    store, fake = _redis_store()
    store.clear_all()
    fake.delete.assert_not_called()


def test_redis_wipe_allowed_only_with_explicit_flag(monkeypatch):
    monkeypatch.setenv(ALLOW_BREAKER_STORE_WIPE_ENV, "1")
    assert redis_breaker_wipe_allowed() is True
    store, fake = _redis_store()
    store.clear_all()
    fake.delete.assert_called_once_with(BREAKER_REDIS_KEY)


def test_redis_wipe_flag_fail_soft_on_delete_error(monkeypatch):
    monkeypatch.setenv(ALLOW_BREAKER_STORE_WIPE_ENV, "true")
    store, fake = _redis_store()
    fake.delete.side_effect = ConnectionError("redis down")
    store.clear_all()  # no lanza


def test_reset_shared_breakers_does_not_delete_redis_without_flag(monkeypatch):
    """reset_shared_breakers contra backend redis inyectado no DEL el HASH paper."""
    fake = MagicMock()
    fake.hgetall.return_value = {
        "system_integrity": '{"active": true, "reason": "D3", "operational_state": "REDUCE_ONLY"}'
    }
    fake.ping.return_value = True
    monkeypatch.setenv("CB_SHARED_STORE", "redis")
    monkeypatch.delenv(ALLOW_BREAKER_STORE_WIPE_ENV, raising=False)
    with patch(
        "app.core.breaker_state_store.RedisBreakerStateStore._redis",
        return_value=fake,
    ):
        reset_shared_breakers()
    fake.delete.assert_not_called()


def test_inmemory_clear_all_still_works_without_flag():
    store = InMemoryBreakerStateStore()
    store.save_breaker(
        "system_integrity",
        trip_record_from_mapping({"active": True, "reason": "t"}),
    )
    store.clear_all()
    assert store.load_all() == {}


# --- B: no HSET closed sobre remote is None ---


def test_persist_closed_does_not_write_when_remote_missing(monkeypatch):
    monkeypatch.setenv(EMPTY_STORE_POLICY_ENV, "fresh")
    store, fake = _redis_store()
    cb = CircuitBreakers(store=store)
    assert cb.breakers["system_integrity"]["active"] is False
    fake.hset.reset_mock()
    cb._persist_breaker("system_integrity")
    fake.hset.assert_not_called()


@pytest.mark.asyncio
async def test_deactivate_missing_key_is_anomaly_does_not_write_closed(
    monkeypatch,
):
    monkeypatch.setenv(EMPTY_STORE_POLICY_ENV, "fresh")
    store, fake = _redis_store()
    cb = CircuitBreakers(store=store)
    fake.hset.reset_mock()
    ok = await cb.deactivate_breaker("system_integrity")
    assert ok is True
    fake.hset.assert_not_called()


@pytest.mark.asyncio
async def test_deactivate_existing_open_still_persists_closed():
    payload = trip_record_from_mapping(
        {"active": True, "reason": "paper", "operational_state": "REDUCE_ONLY"}
    ).to_json()
    store, fake = _redis_store(hgetall={"system_integrity": payload})
    cb = CircuitBreakers(store=store)
    assert cb.is_breaker_active("system_integrity") is True
    fake.hset.reset_mock()
    assert await cb.deactivate_breaker("system_integrity") is True
    fake.hset.assert_called()
    written = fake.hset.call_args[0][2]
    import json

    assert json.loads(written)["active"] is False


# --- A: Redis key ausente = UNKNOWN → fail-closed (default) ---


def test_redis_empty_hydrates_fail_closed_reduce_only():
    store, fake = _redis_store()
    with patch("app.core.circuit_breakers._notify_breaker_store_missing") as notify:
        cb = CircuitBreakers(store=store)
    notify.assert_called_once()
    assert cb.breakers["system_integrity"]["active"] is True
    assert cb.breakers["system_integrity"].get("operational_state") == "REDUCE_ONLY"
    assert STORE_MISSING_REASON in (cb.breakers["system_integrity"].get("reason") or "")
    assert cb._fail_closed_this_process is True
    fake.hset.assert_called()
    import json

    saved = json.loads(fake.hset.call_args[0][2])
    assert saved["active"] is True
    assert saved["operational_state"] == "REDUCE_ONLY"


def test_redis_empty_fresh_policy_stays_closed_no_alert(monkeypatch):
    """Arranque genuinamente nuevo: Desk elige CB_EMPTY_STORE_POLICY=fresh."""
    monkeypatch.setenv(EMPTY_STORE_POLICY_ENV, "fresh")
    store, fake = _redis_store()
    with patch("app.core.circuit_breakers._notify_breaker_store_missing") as notify:
        cb = CircuitBreakers(store=store)
    assert cb.breakers["system_integrity"]["active"] is False
    notify.assert_not_called()
    fake.hset.assert_not_called()


def test_memory_empty_does_not_fail_closed():
    """Store no durable (tests / fallback): vacío sigue CLOSED."""
    store = InMemoryBreakerStateStore()
    cb = CircuitBreakers(store=store)
    assert cb.breakers["system_integrity"]["active"] is False
    assert cb._fail_closed_this_process is False


def test_redis_existing_si_open_not_fail_closed():
    payload = trip_record_from_mapping(
        {
            "active": True,
            "reason": "Demasiadas pérdidas consecutivas: 19",
            "operational_state": "REDUCE_ONLY",
            "activated_at": "2026-08-27T18:55:01.357665",
        }
    ).to_json()
    store, _fake = _redis_store(hgetall={"system_integrity": payload})
    with patch("app.core.circuit_breakers._notify_breaker_store_missing") as notify:
        cb = CircuitBreakers(store=store)
    assert cb.is_breaker_active("system_integrity") is True
    assert cb.breakers["system_integrity"].get("reason", "").startswith("Demasiadas")
    notify.assert_not_called()
    assert cb._fail_closed_this_process is False


def test_redis_read_error_does_not_fail_closed_or_persist():
    """Timeout Redis ≠ HASH borrado: no stamp OPEN encima de un HASH que sigue ahí."""
    store, fake = _redis_store()
    fake.hgetall.side_effect = ConnectionError("timeout")
    with patch("app.core.circuit_breakers._notify_breaker_store_missing") as notify:
        cb = CircuitBreakers(store=store)
    assert cb.breakers["system_integrity"]["active"] is False
    notify.assert_not_called()
    fake.hset.assert_not_called()
    assert cb._fail_closed_this_process is False


def test_fail_closed_gauge_sticky_after_si_reappears():
    from app.core.metrics import breaker_store_missing

    store, fake = _redis_store()
    with patch("app.core.circuit_breakers._notify_breaker_store_missing"):
        cb = CircuitBreakers(store=store)
    assert breaker_store_missing._value.get() == 1
    payload = trip_record_from_mapping(
        {
            "active": True,
            "reason": "Demasiadas pérdidas consecutivas: 19",
            "operational_state": "REDUCE_ONLY",
        }
    ).to_json()
    fake.hgetall.return_value = {"system_integrity": payload}
    cb._hydrate_from_store()
    assert cb._fail_closed_this_process is True
    assert breaker_store_missing._value.get() == 1


def test_persist_closed_missing_increments_anomaly_counter(monkeypatch):
    from app.core.metrics import breaker_store_persist_anomaly_total

    monkeypatch.setenv(EMPTY_STORE_POLICY_ENV, "fresh")
    before = breaker_store_persist_anomaly_total.labels(
        kind="closed_over_missing"
    )._value.get()
    store, fake = _redis_store()
    cb = CircuitBreakers(store=store)
    fake.hset.reset_mock()
    cb._persist_breaker("system_integrity")
    fake.hset.assert_not_called()
    after = breaker_store_persist_anomaly_total.labels(
        kind="closed_over_missing"
    )._value.get()
    assert after == before + 1


def test_empty_store_policy_default_is_fail_closed(monkeypatch):
    from app.core.breaker_state_store import (
        POLICY_FAIL_CLOSED,
        POLICY_FRESH,
        empty_store_policy,
    )

    monkeypatch.delenv(EMPTY_STORE_POLICY_ENV, raising=False)
    assert empty_store_policy() == POLICY_FAIL_CLOSED
    monkeypatch.setenv(EMPTY_STORE_POLICY_ENV, "fresh")
    assert empty_store_policy() == POLICY_FRESH
