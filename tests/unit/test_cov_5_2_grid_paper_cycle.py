"""COV-5.2 — optimized_grid_manager paper cycle residual.

Paper-only · mocks · PROMOTE_LIVE: NO.
Cubre balances SoT, quantities, cycle skip-rebalance, single-asset, factory.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.inventory_controls import (
    IcControlsConfig,
    reset_inventory_control_guard,
)
from app.core.optimized_grid_manager import (
    AssetConfig,
    AssetLimit,
    GridManagerConfig,
    OptimizedGridManager,
    TradingResult,
    create_optimized_grid_manager,
)

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _cfg() -> GridManagerConfig:
    return GridManagerConfig(
        assets={
            "ETHUSDT": AssetConfig(
                symbol="ETHUSDT",
                min_price=1800.0,
                max_price=2200.0,
                grids=10,
                quantity=0.01,
            )
        },
        update_interval=60,
        min_notional_threshold=10.0,
    )


@pytest.fixture
def mgr(paper_env):
    client = MagicMock(name="binance_client")
    client.api_key = "paper-key"
    singleton = MagicMock()
    singleton.client = client
    singleton.get_account_info.return_value = {"accountType": "SPOT", "balances": []}
    with (
        patch(
            "app.services.binance_client_singleton.binance_client_singleton",
            singleton,
        ),
        patch(
            "app.core.optimized_grid_manager.OrderValidator",
            return_value=MagicMock(),
        ),
        patch("app.core.optimized_grid_manager.AsyncBinanceWrapper") as wrap,
    ):
        wrap.return_value.get_price = AsyncMock(return_value=1923.0)
        m = OptimizedGridManager(_cfg())
        m.async_binance.get_price = AsyncMock(return_value=1923.0)
        m.asset_limits["ETHUSDT"] = AssetLimit(
            symbol="ETHUSDT",
            min_qty=0.001,
            max_qty=100.0,
            step_size=0.001,
            min_notional=10.0,
        )
        yield m


@pytest.fixture(autouse=True)
def _reset_ic():
    reset_inventory_control_guard(
        IcControlsConfig(
            enabled_ic1=True,
            enabled_ic2=True,
            symbol="ETHUSDT",
            range_floor=Decimal("1826.92"),
            deployed_capital=Decimal("200"),
        )
    )
    yield
    reset_inventory_control_guard()


async def test_get_asset_balances_paper_sot(mgr):
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_cycle_liquidity.build_paper_balances_from_ledger",
        return_value={"USDT": 500.0, "ETH": 0.05},
    ):
        bals = await mgr.get_asset_balances()
    assert bals["USDT"] == 500.0
    assert bals["ETH"] == 0.05
    mgr.client.get_account.assert_not_called()


async def test_get_current_prices_filters_meta_and_errors(mgr):
    mgr.async_binance.get_price = AsyncMock(
        side_effect=lambda s: (_ for _ in ()).throw(RuntimeError("x"))
        if s == "BADUSDT"
        else 1923.0
    )
    prices = await mgr.get_current_prices(["ETHUSDT", "_meta", "BADUSDT"])
    assert "ETHUSDT" in prices and prices["ETHUSDT"] == 1923.0
    assert "_meta" not in prices
    assert prices.get("BADUSDT", 0) == 0.0


def test_calculate_optimal_quantities_paper_afford(mgr):
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_cycle_liquidity.can_afford_grid_quantity",
        return_value=True,
    ):
        qty = mgr.calculate_optimal_quantities(
            {"ETH": 1.0, "USDT": 1000.0}, {"ETHUSDT": 1923.0}
        )
    assert "ETHUSDT" in qty and qty["ETHUSDT"] > 0

    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_cycle_liquidity.can_afford_grid_quantity",
        return_value=False,
    ):
        empty = mgr.calculate_optimal_quantities(
            {"ETH": 0.0, "USDT": 1.0}, {"ETHUSDT": 1923.0}
        )
    assert empty == {}
    assert "ETHUSDT" in mgr.get_insufficient_funds_report()


async def test_execute_grid_trading_cycle_skips_rebalance_paper_sot(mgr):
    trade = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="BUY",
        quantity=0.01,
        price=1923.0,
        order_id="paper_1",
        status="FILLED",
    )
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch.object(
        mgr, "get_asset_balances", AsyncMock(return_value={"USDT": 500.0, "ETH": 0.1})
    ), patch.object(
        mgr, "get_current_prices", AsyncMock(return_value={"ETHUSDT": 1923.0})
    ), patch(
        "app.core.optimized_grid_manager.strategy_manager.adapt_manager",
        AsyncMock(return_value=None),
    ), patch.object(
        mgr,
        "calculate_optimal_quantities",
        return_value={"ETHUSDT": 0.01},
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "BUY", "level": 1},
    ), patch.object(
        mgr, "_execute_trade", AsyncMock(return_value=trade)
    ), patch(
        "app.services.auto_rebalancer.auto_rebalancer", create=True
    ) as ar:
        results = await mgr.execute_grid_trading_cycle()
    assert len(results) == 1
    assert results[0].order_id == "paper_1"
    ar.get_rebalance_status.assert_not_called()


async def test_execute_single_asset_trading_paths(mgr):
    with patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action",
        return_value=None,
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value=None,
    ):
        assert await mgr._execute_single_asset_trading("ETHUSDT", 0.01, 1923.0) is None

    trade = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="SELL",
        quantity=0.01,
        price=1923.0,
        order_id="paper_2",
        status="FILLED",
    )
    with patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action",
        return_value="BUY",
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "SELL", "level": 2},
    ), patch.object(
        mgr, "_execute_trade", AsyncMock(return_value=trade)
    ):
        out = await mgr._execute_single_asset_trading("ETHUSDT", 0.01, 1923.0)
    assert out is not None and out.action == "SELL"
    assert mgr.config.assets["ETHUSDT"].last_action == "SELL"

    assert await mgr._execute_single_asset_trading("UNKNOWN", 0.01, 1.0) is None


async def test_create_and_reload_configuration(tmp_path: Path, paper_env):
    cfg_path = tmp_path / "grid_cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "_meta": {"v": 1},
                "system_config": {"x": 1},
                "ETHUSDT": {
                    "symbol": "ETHUSDT",
                    "min_price": 1800.0,
                    "max_price": 2200.0,
                    "grids": 10,
                    "quantity": 0.01,
                },
                "update_interval": 30,
                "min_notional_threshold": 10.0,
            }
        )
    )

    client = MagicMock()
    client.api_key = "paper-key"
    singleton = MagicMock(client=client)
    with patch(
        "app.services.binance_client_singleton.binance_client_singleton",
        singleton,
    ), patch(
        "app.core.optimized_grid_manager.OrderValidator", return_value=MagicMock()
    ), patch(
        "app.core.optimized_grid_manager.AsyncBinanceWrapper"
    ), patch.object(
        OptimizedGridManager, "_load_asset_limits", AsyncMock()
    ):
        manager = await create_optimized_grid_manager(str(cfg_path))
    assert manager is not None
    assert "ETHUSDT" in manager.config.assets
    assert "_meta" not in manager.config.assets

    with patch(
        "app.core.optimized_grid_manager.create_optimized_grid_manager",
        AsyncMock(return_value=manager),
    ):
        assert await manager.reload_configuration(str(cfg_path)) is True

    with patch(
        "app.core.optimized_grid_manager.create_optimized_grid_manager",
        AsyncMock(return_value=None),
    ):
        assert await manager.reload_configuration(str(cfg_path)) is False

    bad = await create_optimized_grid_manager(str(tmp_path / "missing.json"))
    assert bad is None


def test_send_trading_notification(mgr):
    result = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="BUY",
        quantity=0.01,
        price=1923.0,
        order_id="p",
        status="FILLED",
    )
    with patch("app.core.optimized_grid_manager.send_telegram_alert") as tg:
        mgr._send_trading_notification(result)
    tg.assert_called()
