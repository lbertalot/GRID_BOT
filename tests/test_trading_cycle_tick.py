from types import SimpleNamespace
from datetime import datetime, timedelta
from typing import Optional

import pytest


class DummyAsyncCache:
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ttl_seconds: int):
        # Guardar como string (simulando serialización en capa real)
        if isinstance(value, dict):
            import json

            self.store[key] = json.dumps(value)
        else:
            self.store[key] = str(value)


@pytest.fixture(autouse=True)
def no_celery_broker_env(monkeypatch):
    # Evitar dependencias externas durante tests
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


@pytest.fixture
def setup_tick(monkeypatch):
    import app.services.trading_tasks as tt

    # Reemplazar cache global
    dummy = DummyAsyncCache()
    monkeypatch.setattr(tt, "_CACHE", dummy, raising=True)

    # Simular MarketDataCollector
    class FakeMDC:
        def __init__(self, ttl_seconds: int = 5):
            pass

        async def get_price(self, symbol: str) -> float:
            return 100.0

        async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 60):
            # [open time, open, high, low, close, volume]
            return [[0, 0, 0, 0, 100.0, 123.0] for _ in range(60)]

    monkeypatch.setattr(tt, "MarketDataCollector", FakeMDC, raising=True)

    # Simular StrategySelector
    class FakeSelector:
        def __init__(self, risk):
            pass

        def select_strategy(self, rp, sym, account_state):
            return SimpleNamespace(strategy_name="GridTrading", confidence=0.7)

    monkeypatch.setattr(tt, "StrategySelector", FakeSelector, raising=True)

    # Simular create_optimized_grid_manager y fund_manager.get_trading_summary
    class FakeManager:
        async def get_asset_balances(self):
            return {"USDT": 100.0}

    async def fake_create_manager(cfg: str):
        return FakeManager()

    async def fake_summary(balances):
        return {"total_value_usdt": 100.0, "usdt_balance": 80.0}

    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", fake_create_manager, raising=True
    )
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(get_trading_summary=fake_summary),
        raising=True,
    )

    return tt, dummy


def _set_cycle_state(
    cache: DummyAsyncCache, started_at: datetime, decisions: Optional[dict] = None
):
    import json

    state = {"started_at": started_at.isoformat(), "decision": decisions or {}}
    cache.store["cycle:state"] = json.dumps(state)


def _get_cycle_state(cache: DummyAsyncCache):
    import json

    raw = cache.store.get("cycle:state")
    return json.loads(raw) if raw else None


def test_evaluation_phase_persists_decision(setup_tick):
    tt, cache = setup_tick

    # Estado: ciclo comenzó hace 10s → fase evaluación
    start = datetime.utcnow() - timedelta(seconds=10)
    _set_cycle_state(cache, start)

    # Ejecutar tick
    tt.trading_cycle_tick()

    state = _get_cycle_state(cache)
    assert state is not None
    assert isinstance(state.get("decision"), dict)
    # Se espera decisiones para símbolos configurados (mock)
    assert len(state["decision"]) >= 1


def test_execution_phase_enqueues_when_no_breakers(setup_tick, monkeypatch):
    tt, cache = setup_tick

    # Estado: ciclo empezó hace 250s (entre 240 y 300) y hay decisión lista
    start = datetime.utcnow() - timedelta(seconds=250)
    _set_cycle_state(cache, start, decisions={"BTCUSDT": {"strategy": "GridTrading"}})

    # Breakers inactivos
    class FakeCB:
        def get_all_breakers_status(self):
            return {"critical_mode": False, "active_breakers": []}

    monkeypatch.setattr(tt, "CircuitBreakers", FakeCB, raising=True)

    # Capturar encolado de ejecución
    called = {"delay": 0}

    class FakeTask:
        @staticmethod
        def delay():
            called["delay"] += 1

    monkeypatch.setattr(tt, "execute_trading_cycle", FakeTask, raising=True)

    tt.trading_cycle_tick()

    assert called["delay"] == 1


def test_execution_skipped_when_breakers_active(setup_tick, monkeypatch):
    tt, cache = setup_tick

    start = datetime.utcnow() - timedelta(seconds=250)
    _set_cycle_state(cache, start, decisions={"BTCUSDT": {"strategy": "GridTrading"}})

    class FakeCB:
        def get_all_breakers_status(self):
            return {"critical_mode": True, "active_breakers": ["system_integrity"]}

    monkeypatch.setattr(tt, "CircuitBreakers", FakeCB, raising=True)

    called = {"delay": 0}

    class FakeTask:
        @staticmethod
        def delay():
            called["delay"] += 1

    monkeypatch.setattr(tt, "execute_trading_cycle", FakeTask, raising=True)

    tt.trading_cycle_tick()

    assert called["delay"] == 0


class _MockCounter:
    """Counter mock que registra cada .labels(...).inc() para aserciones."""

    def __init__(self):
        self.calls: list = []

    def labels(self, **kwargs):
        self._last = kwargs
        return self

    def inc(self):
        self.calls.append(dict(self._last))


def test_ml_disabled_uses_fallback(setup_tick, monkeypatch):
    """Con ML_ENABLED=false el ciclo usa fallback y registra métrica reason=disabled."""
    import app.services.trading_tasks as tt

    monkeypatch.setenv("ML_ENABLED", "false")
    used = _MockCounter()
    fallback = _MockCounter()
    monkeypatch.setattr(tt, "ml_regime_used_in_cycle_total", used, raising=True)
    monkeypatch.setattr(tt, "ml_regime_fallback_total", fallback, raising=True)

    strategy_blacklist = type(
        "FakeBlacklist",
        (),
        {"should_block_trading": lambda self, symbol, strat: (False, "")},
    )()
    monkeypatch.setattr(tt, "strategy_blacklist", strategy_blacklist, raising=True)

    start = datetime.utcnow() - timedelta(seconds=10)
    _set_cycle_state(setup_tick[1], start)
    tt.trading_cycle_tick()

    assert len(used.calls) == 0
    assert len(fallback.calls) >= 1
    assert any(c.get("reason") == "disabled" for c in fallback.calls)


def test_ml_enabled_uses_prediction_when_available(setup_tick, monkeypatch):
    """Con ML_ENABLED=true y predict_regime OK se usa predicción y métrica used."""
    import app.services.trading_tasks as tt
    from app.services.ml_engine import MLEngine, RegimePrediction as MLRegimePrediction

    monkeypatch.setenv("ML_ENABLED", "true")
    used = _MockCounter()
    fallback = _MockCounter()
    monkeypatch.setattr(tt, "ml_regime_used_in_cycle_total", used, raising=True)
    monkeypatch.setattr(tt, "ml_regime_fallback_total", fallback, raising=True)

    async def fake_predict_regime(
        self, symbol: str, interval: str = "1m", limit: int = 60
    ):
        return MLRegimePrediction(label=1, proba=0.8)

    monkeypatch.setattr(MLEngine, "predict_regime", fake_predict_regime, raising=True)
    strategy_blacklist = type(
        "FakeBlacklist",
        (),
        {"should_block_trading": lambda self, symbol, strat: (False, "")},
    )()
    monkeypatch.setattr(tt, "strategy_blacklist", strategy_blacklist, raising=True)

    start = datetime.utcnow() - timedelta(seconds=10)
    _set_cycle_state(setup_tick[1], start)
    tt.trading_cycle_tick()

    assert len(used.calls) >= 1
    assert any(c.get("symbol") == "ETHUSDT" for c in used.calls)


def test_ml_enabled_fallback_on_predict_error(setup_tick, monkeypatch):
    """Con ML_ENABLED=true y predict_regime lanzando, se usa fallback con reason=error."""
    import app.services.trading_tasks as tt
    from app.services.ml_engine import MLEngine

    monkeypatch.setenv("ML_ENABLED", "true")
    used = _MockCounter()
    fallback = _MockCounter()
    monkeypatch.setattr(tt, "ml_regime_used_in_cycle_total", used, raising=True)
    monkeypatch.setattr(tt, "ml_regime_fallback_total", fallback, raising=True)

    async def fake_predict_raise(
        self, symbol: str, interval: str = "1m", limit: int = 60
    ):
        raise RuntimeError("mock ML failure")

    monkeypatch.setattr(MLEngine, "predict_regime", fake_predict_raise, raising=True)
    strategy_blacklist = type(
        "FakeBlacklist",
        (),
        {"should_block_trading": lambda self, symbol, strat: (False, "")},
    )()
    monkeypatch.setattr(tt, "strategy_blacklist", strategy_blacklist, raising=True)

    start = datetime.utcnow() - timedelta(seconds=10)
    _set_cycle_state(setup_tick[1], start)
    tt.trading_cycle_tick()

    assert len(used.calls) == 0
    assert len(fallback.calls) >= 1
    assert any(c.get("reason") == "error" for c in fallback.calls)
