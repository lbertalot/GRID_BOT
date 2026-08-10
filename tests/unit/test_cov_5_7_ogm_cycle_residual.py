"""COV-5.7 — optimized_grid_manager residual: balances exchange + cycle validation.

Paper-only · mocks Binance · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from binance.exceptions import BinanceAPIException
import binance.exceptions as _bexc

# Stub CI a veces no define RequestException
if not hasattr(_bexc, "BinanceRequestException"):

    class BinanceRequestException(Exception):
        pass

    _bexc.BinanceRequestException = BinanceRequestException
else:
    from binance.exceptions import BinanceRequestException

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


async def test_balances_exchange_happy_and_preverified(mgr):
    mgr._account_info = None
    mgr.client.get_account = MagicMock(
        return_value={
            "balances": [
                {"asset": "USDT", "free": "250.5", "locked": "0"},
                {"asset": "ETH", "free": "0.0", "locked": "0"},
                {"asset": "BTC", "free": "0.01", "locked": "0"},
            ]
        }
    )
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        bals = await mgr.get_asset_balances()
    assert bals["USDT"] == 250.5
    assert bals["BTC"] == 0.01
    assert "ETH" not in bals

    mgr._account_info = {
        "balances": [{"asset": "USDT", "free": "10", "locked": "0"}]
    }
    mgr.client.get_account.reset_mock()
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        bals2 = await mgr.get_asset_balances()
    assert bals2 == {"USDT": 10.0}
    mgr.client.get_account.assert_not_called()


async def test_balances_exchange_error_paths(mgr):
    mgr._account_info = None
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        mgr.client = None
        assert await mgr.get_asset_balances() == {}

    client = MagicMock()
    client.api_key = None
    mgr.client = client
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        assert await mgr.get_asset_balances() == {}

    client.api_key = "k"
    for code in (-2015, -2013, -1000):
        client.get_account = MagicMock(
            side_effect=BinanceAPIException(400, f"err-{code}", code=code)
        )
        with patch(
            "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
            return_value=False,
        ):
            assert await mgr.get_asset_balances() == {}

    client.get_account = MagicMock(
        side_effect=BinanceRequestException("net-down")
    )
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        assert await mgr.get_asset_balances() == {}

    client.get_account = MagicMock(side_effect=RuntimeError("boom"))
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        assert await mgr.get_asset_balances() == {}


async def test_balances_paper_exception_falls_back(mgr):
    mgr._account_info = None
    mgr.client.get_account = MagicMock(
        return_value={"balances": [{"asset": "USDT", "free": "7", "locked": "0"}]}
    )
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        side_effect=RuntimeError("ledger-down"),
    ):
        bals = await mgr.get_asset_balances()
    assert bals == {"USDT": 7.0}


async def test_cycle_rebalance_exchange_branches(mgr):
    ar = MagicMock()
    ar.get_rebalance_status = AsyncMock(
        return_value={
            "assets_needing_rebalance": 2,
            "can_rebalance": True,
            "total_needed_usdt": 40,
            "available_usdt": 50,
        }
    )
    ar.check_and_rebalance = AsyncMock(return_value={"status": "success"})

    common = dict(
        get_asset_balances=AsyncMock(return_value={"USDT": 500.0, "ETH": 0.1}),
        get_current_prices=AsyncMock(return_value={"ETHUSDT": 1923.0}),
        calculate_optimal_quantities=MagicMock(return_value={}),
    )

    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ), patch(
        "app.services.auto_rebalancer.auto_rebalancer", ar
    ), patch(
        "app.core.optimized_grid_manager.strategy_manager.adapt_manager",
        AsyncMock(return_value=None),
    ), patch.object(mgr, "get_asset_balances", common["get_asset_balances"]), patch.object(
        mgr, "get_current_prices", common["get_current_prices"]
    ), patch.object(
        mgr, "calculate_optimal_quantities", common["calculate_optimal_quantities"]
    ):
        await mgr.execute_grid_trading_cycle()
    ar.check_and_rebalance.assert_awaited()

    ar.get_rebalance_status = AsyncMock(
        return_value={
            "assets_needing_rebalance": 1,
            "can_rebalance": False,
            "total_needed_usdt": 80,
            "available_usdt": 10,
        }
    )
    ar.check_and_rebalance.reset_mock()
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ), patch(
        "app.services.auto_rebalancer.auto_rebalancer", ar
    ), patch(
        "app.core.optimized_grid_manager.strategy_manager.adapt_manager",
        AsyncMock(return_value=None),
    ), patch.object(mgr, "get_asset_balances", common["get_asset_balances"]), patch.object(
        mgr, "get_current_prices", common["get_current_prices"]
    ), patch.object(
        mgr, "calculate_optimal_quantities", common["calculate_optimal_quantities"]
    ):
        await mgr.execute_grid_trading_cycle()
    ar.check_and_rebalance.assert_not_called()

    ar.get_rebalance_status = AsyncMock(
        return_value={"assets_needing_rebalance": 0, "can_rebalance": True}
    )
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ), patch(
        "app.services.auto_rebalancer.auto_rebalancer", ar
    ), patch(
        "app.core.optimized_grid_manager.strategy_manager.adapt_manager",
        AsyncMock(return_value=None),
    ), patch.object(mgr, "get_asset_balances", common["get_asset_balances"]), patch.object(
        mgr, "get_current_prices", common["get_current_prices"]
    ), patch.object(
        mgr, "calculate_optimal_quantities", common["calculate_optimal_quantities"]
    ):
        await mgr.execute_grid_trading_cycle()

    ar.get_rebalance_status = AsyncMock(side_effect=RuntimeError("rebal-boom"))
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ), patch(
        "app.services.auto_rebalancer.auto_rebalancer", ar
    ), patch(
        "app.core.optimized_grid_manager.strategy_manager.adapt_manager",
        AsyncMock(return_value=None),
    ), patch.object(mgr, "get_asset_balances", common["get_asset_balances"]), patch.object(
        mgr, "get_current_prices", common["get_current_prices"]
    ), patch.object(
        mgr, "calculate_optimal_quantities", common["calculate_optimal_quantities"]
    ):
        out = await mgr.execute_grid_trading_cycle()
    assert out == []


async def test_cycle_validation_bump_and_shortage(mgr):
    trade = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="BUY",
        quantity=0.02,
        price=1923.0,
        order_id="paper_bump",
        status="FILLED",
    )
    fm = MagicMock()
    # 1st: invalid + min_qty; retry: valid
    fm.validate_trade_requirements = AsyncMock(
        side_effect=[
            (False, "too small", {"min_quantity_required": 0.02}),
            (True, "ok", {"quantity": 0.02}),
        ]
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
        AsyncMock(return_value={"ETHUSDT": "wider"}),
    ), patch.object(
        mgr, "calculate_optimal_quantities", return_value={"ETHUSDT": 0.01}
    ), patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action", return_value=None
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "BUY", "level": 1},
    ), patch(
        "app.services.fund_manager.fund_manager", fm
    ), patch.object(
        mgr, "_execute_trade", AsyncMock(return_value=trade)
    ):
        results = await mgr.execute_grid_trading_cycle()
    assert len(results) == 1
    assert fm.validate_trade_requirements.await_count == 2

    # shortage path → reduce qty → still fail → continue (no trade)
    fm2 = MagicMock()
    fm2.validate_trade_requirements = AsyncMock(
        side_effect=[
            (False, "shortage", {"shortage": 5.0}),
            (False, "still short", {"shortage": 4.0}),
        ]
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
        AsyncMock(side_effect=RuntimeError("adapt-fail")),
    ), patch.object(
        mgr, "calculate_optimal_quantities", return_value={"ETHUSDT": 0.01}
    ), patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action", return_value=None
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "BUY", "level": 1},
    ), patch(
        "app.services.fund_manager.fund_manager", fm2
    ), patch.object(
        mgr, "_execute_trade", AsyncMock()
    ) as exec_trade:
        results2 = await mgr.execute_grid_trading_cycle()
    assert results2 == []
    exec_trade.assert_not_called()

    # invalid without shortage → continue
    fm3 = MagicMock()
    fm3.validate_trade_requirements = AsyncMock(
        return_value=(False, "blocked", {})
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
        mgr, "calculate_optimal_quantities", return_value={"ETHUSDT": 0.01}
    ), patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action", return_value=None
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "BUY", "level": 1},
    ), patch(
        "app.services.fund_manager.fund_manager", fm3
    ):
        assert await mgr.execute_grid_trading_cycle() == []

    # shortage 0 → continue
    fm4 = MagicMock()
    fm4.validate_trade_requirements = AsyncMock(
        return_value=(False, "no cash", {"shortage": 0})
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
        mgr, "calculate_optimal_quantities", return_value={"ETHUSDT": 0.01}
    ), patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action", return_value=None
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "BUY", "level": 1},
    ), patch(
        "app.services.fund_manager.fund_manager", fm4
    ):
        assert await mgr.execute_grid_trading_cycle() == []

    # bump fails then shortage succeeds with 0.8 qty
    trade2 = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="BUY",
        quantity=0.008,
        price=1923.0,
        order_id="paper_short",
        status="FILLED",
    )
    fm5 = MagicMock()
    fm5.validate_trade_requirements = AsyncMock(
        side_effect=[
            (False, "too small", {"min_quantity_required": 0.02, "shortage": 1.0}),
            (False, "still", {"shortage": 1.0}),
            (True, "ok", {"quantity": 0.008}),
        ]
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
        mgr, "calculate_optimal_quantities", return_value={"ETHUSDT": 0.01}
    ), patch(
        "app.core.paper_cycle_liquidity.resolve_last_grid_action",
        side_effect=RuntimeError("hydrate-skip"),
    ), patch(
        "app.core.optimized_grid_manager.decide_grid_action",
        return_value={"action": "BUY", "level": 1},
    ), patch(
        "app.services.fund_manager.fund_manager", fm5
    ), patch.object(
        mgr, "_execute_trade", AsyncMock(return_value=trade2)
    ):
        results5 = await mgr.execute_grid_trading_cycle()
    assert len(results5) == 1


def test_get_trading_statistics_with_history(mgr):
    assert "message" in mgr.get_trading_statistics()
    buy = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="BUY",
        quantity=0.01,
        price=1900.0,
        order_id="1",
        status="FILLED",
        profit=0.0,
    )
    sell = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="SELL",
        quantity=0.01,
        price=1950.0,
        order_id="2",
        status="FILLED",
        profit=5.0,
    )
    # TradingResult es dataclass sin .dict(); el código legacy lo espera.
    buy.dict = lambda: {"symbol": buy.symbol, "action": buy.action}  # type: ignore[attr-defined]
    sell.dict = lambda: {"symbol": sell.symbol, "action": sell.action}  # type: ignore[attr-defined]
    mgr.trading_history = [buy, sell]
    stats = mgr.get_trading_statistics()
    assert stats["total_trades"] == 2
    assert stats["buy_trades"] == 1
    assert stats["sell_trades"] == 1
    assert stats["total_profit"] == 5.0
    assert stats["asset_statistics"]["ETHUSDT"]["trades"] == 2


async def test_save_configuration_ok_and_fail(mgr, tmp_path):
    path = tmp_path / "grid_cfg.json"
    assert await mgr.save_configuration(str(path)) is True
    assert path.exists() and "ETHUSDT" in path.read_text()

    with patch("asyncio.to_thread", side_effect=OSError("disk full")):
        assert await mgr.save_configuration(str(tmp_path / "x.json")) is False
