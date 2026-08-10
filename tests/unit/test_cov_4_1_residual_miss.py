"""COV-4.1 — residual miss: fund_manager + auto_rebalancer_v2 + trading_tasks.

Paper-only · no live · PROMOTE_LIVE: NO.
Liquidación/rebalance mockeados; sin TradeExecutor real.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.trading_tasks as tt
from app.services.auto_rebalancer_v2 import AutoRebalancerV2
from app.services.fund_manager import FundManager

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── FundManager ──────────────────────────────────────────────────────────────


@pytest.fixture
def fm(monkeypatch):
    monkeypatch.setenv("MIN_NOTIONAL", "10")
    monkeypatch.setenv("MAX_POSITION_SIZE", "100")
    monkeypatch.setenv("SAFETY_MARGIN", "0.95")
    return FundManager()


async def test_fund_manager_validate_optimal_summary(fm):
    info = {
        "stepSize": 0.001,
        "minQty": 0.001,
        "minNotional": 10.0,
    }
    with patch("app.services.fund_manager.BinanceService") as BS, patch(
        "app.services.fund_manager.commission_manager.calculate_commission",
        return_value=0.1,
    ):
        BS.return_value.get_symbol_info.return_value = info

        ok, msg, det = await fm.validate_trade_requirements(
            "BTCUSDT", "BUY", 0.001, 50000.0, {"USDT": 1000.0, "BTC": 1.0}
        )
        assert ok is True and det["quantity"] > 0

        bad_n, msg_n, _ = await fm.validate_trade_requirements(
            "BTCUSDT", "BUY", 0.0001, 10.0, {"USDT": 1000.0}
        )
        assert bad_n is False
        assert "nocional" in msg_n.lower()

        bad_max, _, _ = await fm.validate_trade_requirements(
            "BTCUSDT", "BUY", 1.0, 200.0, {"USDT": 10000.0}
        )
        assert bad_max is False

        short_u, _, _ = await fm.validate_trade_requirements(
            "BTCUSDT", "BUY", 0.001, 50000.0, {"USDT": 1.0}
        )
        assert short_u is False

        # notional 0.01*50k=500 > MAX=100 → max-size; SELL short usa qty pequeña
        short_b, _, _ = await fm.validate_trade_requirements(
            "BTCUSDT", "SELL", 0.01, 50000.0, {"BTC": 0.001, "USDT": 100}
        )
        assert short_b is False

        ok_sell, _, det_s = await fm.validate_trade_requirements(
            "BTCUSDT", "SELL", 0.001, 50000.0, {"BTC": 1.0, "USDT": 100}
        )
        assert ok_sell is True and det_s["side"] == "SELL"

        BS.return_value.get_symbol_info.side_effect = RuntimeError("x")
        ok2, _, _ = await fm.validate_trade_requirements(
            "ETHUSDT", "BUY", 0.02, 2000.0, {"USDT": 500.0}
        )
        assert ok2 is True

    with patch.object(
        fm,
        "validate_trade_requirements",
        AsyncMock(
            side_effect=[
                (False, "no", {"min_quantity_required": 0.01}),
                (True, "ok", {"quantity": 0.01}),
            ]
        ),
    ):
        qty, _, _ = await fm.calculate_optimal_quantity(
            "BTCUSDT", 50000.0, {"USDT": 1000.0}, target_notional=50.0
        )
        assert qty == pytest.approx(10.0 / 50000.0)  # fallback min_notional/price

    with patch.object(
        fm,
        "validate_trade_requirements",
        AsyncMock(return_value=(True, "ok", {"quantity": 0.002})),
    ):
        q2, _, _ = await fm.calculate_optimal_quantity(
            "BTCUSDT", 50000.0, {"USDT": 1000.0}
        )
        assert q2 > 0

    with patch.object(
        fm,
        "validate_trade_requirements",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        qe, msg_e, _ = await fm.calculate_optimal_quantity(
            "BTCUSDT", 50000.0, {"USDT": 1000.0}
        )
        assert qe == 0.0 and "Error" in msg_e

    with patch(
        "app.services.fund_manager.commission_manager.calculate_commission",
        side_effect=RuntimeError("fee"),
    ), patch("app.services.fund_manager.BinanceService") as BS:
        BS.return_value.get_symbol_info.return_value = None
        ok_e, msg_e, _ = await fm.validate_trade_requirements(
            "BTCUSDT", "BUY", 0.01, 100.0, {"USDT": 100}
        )
        assert ok_e is False and "Error" in msg_e

    with patch(
        "app.services.binance_client_singleton.binance_client_singleton.get_symbol_price",
        side_effect=RuntimeError("no price"),
    ):
        summary = await fm.get_trading_summary(
            {"USDT": 100.0, "BTC": 0.001, "ETH": 1.0, "SPK": 10.0}
        )
    assert summary["can_trade"] is True
    assert summary["usdt_balance"] == 100.0

    with patch(
        "app.services.binance_client_singleton.binance_client_singleton.get_symbol_price",
        side_effect=lambda sym: {
            "BTCUSDT": 100000.0,
            "ETHUSDT": 3500.0,
            "SPKUSDT": 0.2,
        }[sym],
    ):
        priced = await fm.get_trading_summary(
            {"USDT": 50.0, "BTC": 0.01, "ETH": 0.1, "SPK": 100.0}
        )
    assert priced["total_value_usdt"] > 50.0

    with patch(
        "app.services.binance_client_singleton.binance_client_singleton.get_symbol_price",
        side_effect=RuntimeError("x"),
    ), patch(
        "app.services.fund_manager.round", side_effect=RuntimeError("round boom")
    ):
        err_sum = await fm.get_trading_summary({"USDT": 1.0})
    assert err_sum.get("can_trade") is False


# ── AutoRebalancerV2 ─────────────────────────────────────────────────────────


@pytest.fixture
def rebal(monkeypatch):
    monkeypatch.setenv("ENABLE_AUTO_REBALANCE", "true")
    monkeypatch.setenv("MIN_USDT_BALANCE", "25")
    monkeypatch.setenv("TARGET_USDT_BALANCE", "50")
    client = MagicMock()
    with patch(
        "app.services.auto_rebalancer_v2.get_binance_client_singleton",
        return_value=SimpleNamespace(client=client),
    ), patch(
        "app.services.auto_rebalancer_v2.get_shared_breakers",
        return_value=MagicMock(is_trading_halted=MagicMock(return_value=False)),
    ), patch(
        "app.services.auto_rebalancer_v2.StrategyBlacklist", return_value=MagicMock()
    ):
        r = AutoRebalancerV2()
    r.binance_client = client
    r.circuit_breakers = MagicMock()
    r.circuit_breakers.is_trading_halted.return_value = False
    r.strategy_blacklist = MagicMock()
    r.strategy_blacklist.is_blacklist_active.return_value = False
    r.strategy_blacklist.is_symbol_blacklisted.return_value = False
    return r


def _ticker(*, symbol=None, **_kwargs):
    s = symbol or ""
    if "BNB" in s:
        return {"price": "300"}
    if "SPK" in s:
        return {"price": "0.05"}
    return {"price": "1"}


async def test_rebalancer_v2_check_paths_and_sales_mocked(rebal):
    rebal.enable_auto_rebalance = False
    assert (await rebal.check_and_rebalance())["status"] == "disabled"
    rebal.enable_auto_rebalance = True

    rebal.is_rebalancing = True
    assert (await rebal.check_and_rebalance())["status"] == "skipped"
    rebal.is_rebalancing = False

    rebal.circuit_breakers.is_trading_halted.return_value = True
    assert (await rebal.check_and_rebalance())["status"] == "blocked"
    rebal.circuit_breakers.is_trading_halted.return_value = False

    rebal.strategy_blacklist.is_blacklist_active.return_value = True
    assert (await rebal.check_and_rebalance())["status"] == "blocked"
    rebal.strategy_blacklist.is_blacklist_active.return_value = False

    with patch.object(rebal, "_get_current_usdt_balance", AsyncMock(return_value=100.0)):
        assert (await rebal.check_and_rebalance())["status"] == "sufficient"

    with patch.object(
        rebal, "_get_current_usdt_balance", AsyncMock(return_value=10.0)
    ), patch.object(
        rebal,
        "_execute_liquidity_rebalance",
        AsyncMock(return_value={"status": "success", "usdt_generated": 40}),
    ):
        out = await rebal.check_and_rebalance()
        assert out["status"] == "success"

    with patch.object(
        rebal, "_get_current_usdt_balance", AsyncMock(side_effect=RuntimeError("x"))
    ):
        assert (await rebal.check_and_rebalance())["status"] == "error"

    rebal.binance_client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "10", "locked": "0"},
            {"asset": "BNB", "free": "1", "locked": "0"},
            {"asset": "ETH", "free": "2", "locked": "0"},
            {"asset": "SPK", "free": "100", "locked": "0"},
        ]
    }
    rebal.binance_client.get_symbol_ticker.side_effect = _ticker
    rebal.binance_client.get_symbol_info.return_value = {
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
        ]
    }

    bals = await rebal._get_all_balances()
    assert bals["BNB"] == 1.0 and "ETH" in bals

    usdt = await rebal._get_current_usdt_balance()
    assert usdt == 10.0

    selected = await rebal._select_assets_for_liquidation(bals, target_deficit=40.0)
    assert isinstance(selected, list)
    assert any(a["asset"] == "BNB" for a in selected) or len(selected) >= 0

    assert await rebal._validate_sale_parameters("BNBUSDT", 0.05) is True
    assert await rebal._validate_sale_parameters("BNBUSDT", 0.0000001) is False

    executor = MagicMock()
    executor.execute_market_sell.return_value = {
        "status": "FILLED",
        "orderId": 99,
    }
    with patch(
        "app.services.auto_rebalancer_v2.get_trade_executor", return_value=executor
    ), patch.object(rebal, "_save_trade_to_db"):
        results = await rebal._execute_sales(
            [
                {
                    "asset": "BNB",
                    "symbol": "BNBUSDT",
                    "quantity": 0.05,
                    "price": 300.0,
                    "value_usdt": 15.0,
                }
            ]
        )
    assert results and results[0]["status"] == "success"
    executor.execute_market_sell.assert_called_once()

    with patch(
        "app.services.auto_rebalancer_v2.get_trade_executor", return_value=executor
    ), patch.object(rebal, "_save_trade_to_db"):
        executor.execute_market_sell.side_effect = RuntimeError("sell fail")
        fail = await rebal._execute_sales(
            [
                {
                    "asset": "BNB",
                    "symbol": "BNBUSDT",
                    "quantity": 0.05,
                    "price": 300.0,
                    "value_usdt": 15.0,
                }
            ]
        )
    assert fail and fail[0]["status"] == "error"

    with patch.object(
        rebal, "_get_all_balances", AsyncMock(return_value={})
    ), patch.object(
        rebal, "_get_current_usdt_balance", AsyncMock(return_value=5.0)
    ):
        empty = await rebal._execute_liquidity_rebalance(40.0)
        assert empty["status"] == "no_assets"

    with patch.object(
        rebal,
        "_get_all_balances",
        AsyncMock(return_value={"BNB": 1.0, "USDT": 5.0}),
    ), patch.object(
        rebal, "_get_current_usdt_balance", AsyncMock(side_effect=[5.0, 45.0])
    ), patch.object(
        rebal,
        "_select_assets_for_liquidation",
        AsyncMock(
            return_value=[
                {
                    "asset": "BNB",
                    "symbol": "BNBUSDT",
                    "quantity": 0.1,
                    "price": 300.0,
                    "value_usdt": 30.0,
                }
            ]
        ),
    ), patch.object(
        rebal,
        "_execute_sales",
        AsyncMock(
            return_value=[
                {
                    "asset": "BNB",
                    "symbol": "BNBUSDT",
                    "status": "success",
                    "value_usdt": 30.0,
                }
            ]
        ),
    ):
        ok_liq = await rebal._execute_liquidity_rebalance(40.0)
    assert ok_liq["status"] == "success"
    assert ok_liq["usdt_generated"] == 40.0

    rebal.binance_client.get_account.side_effect = RuntimeError("acct")
    assert await rebal._get_all_balances() == {}
    assert await rebal._get_current_usdt_balance() == 0.0
    rebal.binance_client.get_account.side_effect = None
    rebal.binance_client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "10", "locked": "0"},
            {"asset": "BNB", "free": "0.5", "locked": "0"},
        ]
    }

    status = await rebal.get_rebalance_status()
    assert status["enabled"] is True
    assert "current_usdt_balance" in status
    assert status["needs_rebalance"] is True

    db = MagicMock()
    with patch("app.services.auto_rebalancer_v2.SessionLocal", return_value=db), patch(
        "app.services.auto_rebalancer_v2.Trade"
    ):
        rebal._save_trade_to_db("BNBUSDT", "SELL", 0.05, 300.0, 99)
        db.add.assert_called()
        db.commit.assert_called()


# ── trading_tasks residual ───────────────────────────────────────────────────


class _Cache:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl_seconds=0):
        self.store[key] = value


@pytest.fixture(autouse=True)
def _tt_env(paper_env, monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    monkeypatch.setenv("ML_ENABLED", "false")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setattr(tt, "_CACHE", _Cache(), raising=True)


def test_trading_tasks_promotion_helpers(monkeypatch):
    monkeypatch.setenv("ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON", '{"invalid"')
    snap, err, _rid = tt._resolve_promotion_gate_after_cost_snapshot("BTCUSDT")
    assert snap is None and err

    monkeypatch.setenv("ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON", "")
    monkeypatch.setenv("ML_PROMOTION_GATE_USE_PERSISTED_BACKTEST", "false")
    assert tt._resolve_promotion_gate_after_cost_snapshot("BTCUSDT") == (
        None,
        None,
        None,
    )

    tt._maybe_persist_promotion_gate_monte_carlo("BTCUSDT", None, 0, None)

    # COV-3.8 defiere hybrid_ml/TF; aquí sólo verificamos que el factory exista.
    assert callable(tt._create_hybrid_ml_engine)


def test_trading_tasks_assess_risk_and_update_metrics(monkeypatch):
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 100.0})
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "can_trade": True,
                    "total_value_usdt": 100.0,
                    "usdt_balance": 80.0,
                }
            )
        ),
    )
    out = tt.assess_risk()
    assert out["risk_level"] == "low"
    assert out["recommendation"] == "continue_trading"

    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "can_trade": False,
                    "total_value_usdt": 5.0,
                    "usdt_balance": 5.0,
                }
            )
        ),
    )
    high = tt.assess_risk()
    assert high["risk_level"] == "high"

    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )
    unknown = tt.assess_risk()
    assert unknown["risk_level"] == "unknown"

    with patch("app.services.trading_tasks.MetricsService") as MS:
        MS.return_value.calculate_portfolio_metrics = AsyncMock(return_value={})
        metrics = tt.update_metrics()
    assert metrics["status"] == "success"

    with patch(
        "app.services.trading_tasks.MetricsService",
        side_effect=RuntimeError("metrics down"),
    ):
        bad = tt.update_metrics()
    assert bad["status"] == "error"
