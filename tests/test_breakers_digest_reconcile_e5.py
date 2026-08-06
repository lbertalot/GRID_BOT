"""E5 — digest / get_breakers_status / cycle: misma fuente Redis shared."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.breaker_state_store import InMemoryBreakerStateStore
from app.core.breakers_status import get_active_breaker_names, get_breakers_status
from app.core.circuit_breakers import CircuitBreakers, reset_shared_breakers


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CB_SHARED_STORE", "memory")
    reset_shared_breakers()
    yield
    reset_shared_breakers()


@pytest.mark.asyncio
async def test_digest_any_open_matches_cycle_when_store_empty():
    """Si el cycle ve active_breakers=[], digest.any_open debe ser False (no AT_RISK RISK)."""
    store = InMemoryBreakerStateStore()
    worker = CircuitBreakers(store=store)
    api = CircuitBreakers(store=store)

    cycle_active = worker.get_all_breakers_status()["active_breakers"]
    assert cycle_active == []

    # Simula que digest/API leen la misma store (proceso distinto)
    from app.core import circuit_breakers as cb_mod

    cb_mod._shared_breakers = api
    status = get_breakers_status()
    assert status["any_open"] is False
    assert status["open_breakers"] == []
    assert get_active_breaker_names() == []


@pytest.mark.asyncio
async def test_worker_trip_visible_identically_in_digest_and_cycle():
    store = InMemoryBreakerStateStore()
    worker = CircuitBreakers(store=store)
    api = CircuitBreakers(store=store)

    await worker.activate_breaker("system_integrity", "e5 paper test")
    cycle_active = worker.get_all_breakers_status()["active_breakers"]
    assert "system_integrity" in cycle_active

    from app.core import circuit_breakers as cb_mod

    cb_mod._shared_breakers = api
    status = get_breakers_status()
    assert status["any_open"] is True
    assert "system_integrity" in status["open_breakers"]
    assert set(get_active_breaker_names()) == set(cycle_active)


def test_cycle_log_uses_active_breakers_not_activation_results(monkeypatch):
    """Regresión: no WARNING con lista vacía engañosa (breakers_activated)."""
    calls = []

    class FakeLogger:
        def warning(self, msg, *a, **k):
            calls.append(("warning", str(msg) % a if a else str(msg)))

        def info(self, msg, *a, **k):
            calls.append(("info", str(msg) % a if a else str(msg)))

        def error(self, msg, *a, **k):
            calls.append(("error", str(msg)))

        def debug(self, msg, *a, **k):
            pass

    from app.core import breakers_status as bs

    monkeypatch.setattr(bs, "logger", FakeLogger())

    from app.core.breakers_status import log_cycle_breakers_status

    log_cycle_breakers_status(active_breakers=[], newly_activated=[])
    assert any(lvl == "info" for lvl, _ in calls)
    assert not any(lvl == "warning" for lvl, _ in calls)

    calls.clear()
    log_cycle_breakers_status(
        active_breakers=["system_integrity"], newly_activated=[]
    )
    assert any(lvl == "warning" and "system_integrity" in msg for lvl, msg in calls)
