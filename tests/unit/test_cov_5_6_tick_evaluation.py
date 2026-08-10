"""COV-5.6 — trading_cycle_tick fase evaluación (0–240s) residual.

Paper-only · lock degradado · PROMOTE_LIVE: NO.
Cubre Kelly sentiment, ML gate/fallback, breakers, decision_ready.
"""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

import app.services.trading_tasks as tt

pytestmark = [pytest.mark.usefixtures("paper_env")]


class _Cache:
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ttl_seconds: int = 0):
        self.store[key] = (
            json.dumps(value) if isinstance(value, dict) else str(value)
        )


@pytest.fixture(autouse=True)
def _paper_celery_env(paper_env, monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    monkeypatch.setenv("ML_ENABLED", "false")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("KELLY_SENTIMENT_SCALE_ENABLED", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "false")
    monkeypatch.setattr(tt, "_CACHE", _Cache(), raising=True)
    monkeypatch.setattr(
        "app.core.distributed_lock.get_redis_client",
        MagicMock(side_effect=RedisError("cov-5.6-no-redis")),
    )


def _state(elapsed_s: float, decision=None):
    started = (datetime.utcnow() - timedelta(seconds=elapsed_s)).isoformat()
    return {"started_at": started, "decision": decision}


def _mdc(price=2000.0):
    mdc = MagicMock()
    mdc.get_price = AsyncMock(return_value=price)
    mdc.get_klines = AsyncMock(
        return_value=[[0, "1", "1", "1", "1", "1"] for _ in range(30)]
    )
    return mdc


def _selector(confidence=0.8):
    selector = MagicMock()
    selector.select_strategy.return_value = SimpleNamespace(
        strategy_name=SimpleNamespace(value="grid"),
        confidence=confidence,
    )
    return selector


def _breakers(critical=False, active=None, newly=None):
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": critical,
        "active_breakers": active or [],
    }
    auto_cb = MagicMock()
    auto_cb.check_and_activate_breakers = AsyncMock(
        return_value={
            "breakers_activated": newly or [],
            "reasons": ["cov"] if newly else [],
        }
    )
    return breakers, auto_cb


def _fund():
    return SimpleNamespace(
        get_trading_summary=AsyncMock(
            return_value={
                "total_value_usdt": 200.0,
                "usdt_balance": 100.0,
                "can_trade": True,
            }
        )
    )


@contextmanager
def _eval_ctx(
    *,
    state,
    set_st,
    mdc=None,
    selector=None,
    breakers=None,
    auto_cb=None,
    mgr=None,
    risk=None,
    fund=None,
    paper_summary=None,
    paper_side_effect=None,
    extra_patches=None,
):
    bl = MagicMock()
    bl.should_block_trading.return_value = (False, "")
    if breakers is None or auto_cb is None:
        breakers, auto_cb = _breakers()
    if mgr is None:
        mgr = MagicMock()
        mgr.get_asset_balances = AsyncMock(return_value={"USDT": 100.0})
    risk = risk or MagicMock(fractional_kelly=0.25)
    if paper_side_effect is not None:
        paper_patch = patch(
            "app.core.paper_trading.get_paper_portfolio_summary",
            side_effect=paper_side_effect,
        )
    else:
        paper_patch = patch(
            "app.core.paper_trading.get_paper_portfolio_summary",
            return_value=paper_summary or {"current_balance": 100.0},
        )
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state))
        )
        stack.enter_context(patch.object(tt, "_set_cycle_state", set_st))
        stack.enter_context(
            patch.object(tt, "MarketDataCollector", return_value=mdc or _mdc())
        )
        stack.enter_context(patch.object(tt, "strategy_blacklist", bl))
        stack.enter_context(
            patch.object(
                tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
            )
        )
        stack.enter_context(patch.object(tt, "fund_manager", fund or _fund()))
        stack.enter_context(patch.object(tt, "auto_circuit_breaker", auto_cb))
        stack.enter_context(patch.object(tt, "get_shared_breakers", lambda: breakers))
        stack.enter_context(patch.object(tt, "RiskManager", return_value=risk))
        stack.enter_context(
            patch.object(tt, "StrategySelector", return_value=selector or _selector())
        )
        stack.enter_context(paper_patch)
        for p in extra_patches or []:
            stack.enter_context(p)
        yield


def test_eval_account_fetch_failure_continues(monkeypatch):
    set_st = AsyncMock()
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(side_effect=RuntimeError("bal-fail"))
    with _eval_ctx(state=_state(60), set_st=set_st, mgr=mgr):
        out = tt.trading_cycle_tick()
    assert out["status"] == "ok"
    set_st.assert_awaited()


def test_eval_breakers_newly_activated_critical(monkeypatch):
    set_st = AsyncMock()
    breakers, auto_cb = _breakers(
        critical=True, active=["system_integrity"], newly=["system_integrity"]
    )
    with _eval_ctx(
        state=_state(90), set_st=set_st, breakers=breakers, auto_cb=auto_cb
    ):
        out = tt.trading_cycle_tick()
    assert out["status"] == "ok"
    saved = set_st.await_args.args[0]
    assert saved["decision"]["ETHUSDT"]["ready"] is False


def test_eval_breakers_check_exception(monkeypatch):
    set_st = AsyncMock()
    auto_cb = MagicMock()
    auto_cb.check_and_activate_breakers = AsyncMock(side_effect=RuntimeError("cb-boom"))
    with _eval_ctx(
        state=_state(45), set_st=set_st, breakers=MagicMock(), auto_cb=auto_cb
    ):
        assert tt.trading_cycle_tick()["status"] == "ok"


def test_eval_kelly_sentiment_bands(monkeypatch):
    monkeypatch.setenv("KELLY_SENTIMENT_SCALE_ENABLED", "true")
    risk = MagicMock(fractional_kelly=0.25)

    set_st = AsyncMock()
    with patch(
        "app.services.promotion_gate_sentiment.resolve_promotion_gate_sentiment_score",
        AsyncMock(return_value=None),
    ), patch(
        "app.services.promotion_gate_sentiment.kelly_multiplier_from_sentiment_score",
        return_value=1.0,
    ), _eval_ctx(state=_state(70), set_st=set_st, risk=risk):
        assert tt.trading_cycle_tick()["status"] == "ok"

    set_st = AsyncMock()
    with patch(
        "app.services.promotion_gate_sentiment.resolve_promotion_gate_sentiment_score",
        AsyncMock(return_value=-0.8),
    ), patch(
        "app.services.promotion_gate_sentiment.kelly_multiplier_from_sentiment_score",
        return_value=0.7,
    ), _eval_ctx(state=_state(75), set_st=set_st, risk=risk):
        assert tt.trading_cycle_tick()["status"] == "ok"
    assert risk.fractional_kelly < 0.25

    risk.fractional_kelly = 0.25
    set_st = AsyncMock()
    with patch(
        "app.services.promotion_gate_sentiment.resolve_promotion_gate_sentiment_score",
        AsyncMock(return_value=0.9),
    ), patch(
        "app.services.promotion_gate_sentiment.kelly_multiplier_from_sentiment_score",
        side_effect=ValueError("bad-mult"),
    ), _eval_ctx(state=_state(80), set_st=set_st, risk=risk):
        assert tt.trading_cycle_tick()["status"] == "ok"

    # scaled_up band
    risk.fractional_kelly = 0.25
    set_st = AsyncMock()
    with patch(
        "app.services.promotion_gate_sentiment.resolve_promotion_gate_sentiment_score",
        AsyncMock(return_value=0.9),
    ), patch(
        "app.services.promotion_gate_sentiment.kelly_multiplier_from_sentiment_score",
        return_value=1.2,
    ), _eval_ctx(state=_state(85), set_st=set_st, risk=risk):
        assert tt.trading_cycle_tick()["status"] == "ok"
    assert risk.fractional_kelly > 0.25


def test_eval_ml_promotion_gate_blocked(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    set_st = AsyncMock()
    hybrid = MagicMock()
    hybrid.predict_regime_from_klines = AsyncMock()
    with _eval_ctx(
        state=_state(100),
        set_st=set_st,
        extra_patches=[
            patch.object(tt, "_create_hybrid_ml_engine", return_value=hybrid),
            patch.object(
                tt,
                "_promotion_gate_allows_ml",
                AsyncMock(return_value=(False, ("oos_fail",))),
            ),
        ],
    ):
        out = tt.trading_cycle_tick()
    assert out["status"] == "ok"
    hybrid.predict_regime_from_klines.assert_not_called()
    assert set_st.await_args.args[0]["decision"]["ETHUSDT"]["regime"] == "RANGE"


def test_eval_ml_predict_success_and_error(monkeypatch):
    from app.core.risk_manager import MarketRegime, RegimePrediction

    monkeypatch.setenv("ML_ENABLED", "true")
    set_st = AsyncMock()
    hybrid = MagicMock()
    hybrid.predict_regime_from_klines = AsyncMock(
        return_value=RegimePrediction(
            long_regime=MarketRegime.BULL_TREND,
            short_regime=MarketRegime.BULL_TREND,
            long_conf=0.9,
            short_conf=0.85,
        )
    )
    with _eval_ctx(
        state=_state(110),
        set_st=set_st,
        extra_patches=[
            patch.object(tt, "_create_hybrid_ml_engine", return_value=hybrid),
            patch.object(
                tt, "_promotion_gate_allows_ml", AsyncMock(return_value=(True, ()))
            ),
        ],
    ):
        assert tt.trading_cycle_tick()["status"] == "ok"
    hybrid.predict_regime_from_klines.assert_awaited()

    set_st = AsyncMock()
    hybrid.predict_regime_from_klines = AsyncMock(side_effect=RuntimeError("ml-down"))
    with _eval_ctx(
        state=_state(120),
        set_st=set_st,
        extra_patches=[
            patch.object(tt, "_create_hybrid_ml_engine", return_value=hybrid),
            patch.object(
                tt, "_promotion_gate_allows_ml", AsyncMock(return_value=(True, ()))
            ),
        ],
    ):
        assert tt.trading_cycle_tick()["status"] == "ok"
    assert set_st.await_args.args[0]["decision"]["ETHUSDT"]["regime"] == "RANGE"


def test_eval_ml_engine_none_raises_fallback(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    set_st = AsyncMock()
    with _eval_ctx(
        state=_state(115),
        set_st=set_st,
        extra_patches=[
            patch.object(tt, "_create_hybrid_ml_engine", return_value=None),
            patch.object(
                tt, "_promotion_gate_allows_ml", AsyncMock(return_value=(True, ()))
            ),
        ],
    ):
        assert tt.trading_cycle_tick()["status"] == "ok"
    assert set_st.await_args.args[0]["decision"]["ETHUSDT"]["regime"] == "RANGE"


def test_eval_symbol_exception_continues(monkeypatch):
    set_st = AsyncMock()
    mdc = _mdc()
    mdc.get_price = AsyncMock(side_effect=RuntimeError("price-boom"))
    with _eval_ctx(state=_state(55), set_st=set_st, mdc=mdc):
        out = tt.trading_cycle_tick()
    assert out["status"] == "ok"
    saved = set_st.await_args.args[0]
    assert not (saved.get("decision") or {}).get("ETHUSDT")


def test_eval_decision_ready_near_four_minutes(monkeypatch):
    set_st = AsyncMock()
    with _eval_ctx(
        state=_state(220), set_st=set_st, selector=_selector(confidence=0.9)
    ):
        out = tt.trading_cycle_tick()
    assert out["status"] == "ok"
    assert set_st.await_args.args[0]["decision"]["ETHUSDT"]["ready"] is True


def test_eval_paper_summary_exception_ignored(monkeypatch):
    set_st = AsyncMock()
    with _eval_ctx(
        state=_state(40),
        set_st=set_st,
        paper_side_effect=RuntimeError("paper-down"),
    ):
        assert tt.trading_cycle_tick()["status"] == "ok"


def test_tick_outer_exception_returns_error(monkeypatch):
    with patch.object(
        tt, "_get_cycle_state", AsyncMock(side_effect=RuntimeError("tick-boom"))
    ):
        out = tt.trading_cycle_tick()
    assert out["status"] == "error"
    assert "tick-boom" in out["message"]
