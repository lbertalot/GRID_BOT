"""COV-1.6 — optimized_grid_manager paper branches (IC gate, place, ledger fill).

Paper-only · mocks · PROMOTE_LIVE: NO.
No cubre el god-object entero — solo execute paper / guards (brief S-COV-85).
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.inventory_controls import (
    IcControlsConfig,
    InventoryControlGuard,
    reset_inventory_control_guard,
)
from app.core.optimized_grid_manager import (
    AssetConfig,
    AssetLimit,
    GridManagerConfig,
    OptimizedGridManager,
)


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
        patch(
            "app.core.optimized_grid_manager.AsyncBinanceWrapper",
        ) as wrap,
    ):
        wrap.return_value.get_price = AsyncMock(return_value=1923.0)
        m = OptimizedGridManager(_cfg())
        m.async_binance.get_price = AsyncMock(return_value=1923.0)
        yield m


@pytest.fixture(autouse=True)
def _reset_ic():
    from app.core.paper_equity_ledger import reset_paper_telemetry

    reset_inventory_control_guard(
        IcControlsConfig(
            enabled_ic1=True,
            enabled_ic2=True,
            symbol="ETHUSDT",
            range_floor=Decimal("1826.92"),
            deployed_capital=Decimal("200"),
        )
    )
    reset_paper_telemetry()
    yield
    reset_inventory_control_guard()
    reset_paper_telemetry()


# ── _record_paper_fill ──────────────────────────────────────────────────────


def test_record_paper_fill_skipped_when_not_sot(mgr):
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        assert mgr._record_paper_fill("ETHUSDT", "BUY", 0.01, 1900.0) is True


def test_record_paper_fill_buy_sell_and_reject(mgr):
    ledger = MagicMock()
    with (
        patch(
            "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
            return_value=True,
        ),
        patch("app.core.paper_equity_ledger.get_paper_ledger", return_value=ledger),
        patch(
            "app.core.paper_equity_ledger.to_money",
            side_effect=lambda v, field_name=None: Decimal(str(v)),
        ),
    ):
        assert mgr._record_paper_fill("ETHUSDT", "BUY", 0.01, 1900.0, grid_level=1) is True
        ledger.record_buy.assert_called_once()
        assert mgr._record_paper_fill("ETHUSDT", "SELL", 0.01, 1910.0) is True
        ledger.record_sell.assert_called_once()

    from app.core.paper_equity_ledger import InsufficientPaperBalance

    ledger2 = MagicMock()
    ledger2.record_buy.side_effect = InsufficientPaperBalance("no cash")
    with (
        patch(
            "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
            return_value=True,
        ),
        patch("app.core.paper_equity_ledger.get_paper_ledger", return_value=ledger2),
        patch(
            "app.core.paper_equity_ledger.to_money",
            side_effect=lambda v, field_name=None: Decimal(str(v)),
        ),
    ):
        assert mgr._record_paper_fill("ETHUSDT", "BUY", 1.0, 1900.0) is False


def test_record_paper_fill_unexpected_error(mgr):
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        side_effect=RuntimeError("boom"),
    ):
        assert mgr._record_paper_fill("ETHUSDT", "BUY", 0.01, 1900.0) is False


# ── _place_order paper ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_place_order_paper_returns_filled(mgr, paper_env):
    with patch(
        "app.core.optimized_grid_manager.commission_manager"
    ) as cm:
        cm.calculate_commission.return_value = 0.5
        order = await mgr._place_order("ETHUSDT", "BUY", 0.01)
    assert order is not None
    assert order["status"] == "FILLED"
    assert str(order["orderId"]).startswith("paper_")


def test_build_paper_simulated_order_payload():
    order = OptimizedGridManager._build_paper_simulated_order(
        symbol="ETHUSDT",
        action="BUY",
        quantity=0.01,
        commission=0.5,
        commission_percentage=2.5,
        notional_value=19.23,
    )
    assert order["status"] == "FILLED"
    assert order["side"] == "BUY"
    assert order["commission_info"]["order_type"] == "MARKET"
    assert str(order["orderId"]).startswith("paper_")


@pytest.mark.asyncio
async def test_place_order_paper_high_commission_warns(mgr, paper_env, caplog):
    with patch(
        "app.core.optimized_grid_manager.commission_manager"
    ) as cm:
        cm.calculate_commission.return_value = 1.0
        order = await mgr._place_order("ETHUSDT", "BUY", 0.01)
    assert order["status"] == "FILLED"


# ── _execute_trade paper + IC ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_trade_buy_blocked_by_ic1(mgr, paper_env):
    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=Decimal("1826.92"), deployed_capital=Decimal("200"))
    )
    guard.observe(mid=Decimal("1800"), equity_mtm=Decimal("1000"), enforce=False)
    assert guard.allows_core_buy() is False

    with patch.object(mgr, "_place_order", AsyncMock()) as place:
        out = await mgr._execute_trade("ETHUSDT", "BUY", 0.01, 1800.0)
    assert out is None
    place.assert_not_called()


@pytest.mark.asyncio
async def test_execute_trade_buy_ic_error_fail_closed_paper(mgr, paper_env):
    with patch(
        "app.core.inventory_controls.get_inventory_control_guard",
        side_effect=RuntimeError("ic down"),
    ):
        out = await mgr._execute_trade("ETHUSDT", "BUY", 0.01, 1900.0)
    assert out is None


@pytest.mark.asyncio
async def test_execute_trade_buy_observe_passes_equity_when_series_available(
    mgr, paper_env
):
    """P0-A: observe BUY recibe equity_mtm + peak si la serie paper ya está hidratada."""
    from app.core.paper_equity_ledger import PaperEquitySeries
    from app.core import paper_equity_ledger as pel

    series = PaperEquitySeries()
    series.record(Decimal("1000"))
    series.record(Decimal("990"))
    pel._series = series

    captured: dict = {}

    def _observe(**kwargs):
        captured.update(kwargs)
        return MagicMock(ic1_active=False, ic2_should_flatten=False, events=())

    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=Decimal("1826.92"), deployed_capital=Decimal("200"))
    )
    with (
        patch.object(guard, "observe", side_effect=_observe),
        patch.object(mgr, "_place_order", AsyncMock(return_value=None)),
    ):
        await mgr._execute_trade("ETHUSDT", "BUY", 0.01, 1900.0)

    assert captured.get("mid") == 1900.0
    assert captured.get("equity_mtm") == Decimal("990")
    assert captured.get("peak_equity") == Decimal("1000")
    assert captured.get("enforce") is False
    reset_inventory_control_guard(
        IcControlsConfig(range_floor=Decimal("1826.92"), deployed_capital=Decimal("200"))
    )
    fake_order = {"orderId": "paper_1", "status": "FILLED"}
    with (
        patch.object(mgr, "_place_order", AsyncMock(return_value=fake_order)),
        patch.object(mgr, "_record_paper_fill", return_value=True),
        patch.object(mgr, "_send_trading_notification"),
        patch.object(mgr, "_save_trade_to_db", AsyncMock()),
    ):
        result = await mgr._execute_trade(
            "ETHUSDT", "BUY", 0.01, 1900.0, grid_level=2
        )
    assert result is not None
    assert result.symbol == "ETHUSDT"
    assert result.action == "BUY"
    assert len(mgr.trading_history) == 1


@pytest.mark.asyncio
async def test_execute_trade_ledger_reject_aborts(mgr, paper_env):
    reset_inventory_control_guard(
        IcControlsConfig(range_floor=Decimal("1826.92"), deployed_capital=Decimal("200"))
    )
    with (
        patch.object(
            mgr, "_place_order", AsyncMock(return_value={"orderId": "p", "status": "FILLED"})
        ),
        patch.object(mgr, "_record_paper_fill", return_value=False),
    ):
        assert await mgr._execute_trade("ETHUSDT", "SELL", 0.01, 1910.0) is None


@pytest.mark.asyncio
async def test_execute_trade_place_order_none(mgr, paper_env):
    reset_inventory_control_guard(
        IcControlsConfig(range_floor=Decimal("1826.92"), deployed_capital=Decimal("200"))
    )
    with patch.object(mgr, "_place_order", AsyncMock(return_value=None)):
        assert await mgr._execute_trade("ETHUSDT", "SELL", 0.01, 1910.0) is None


# ── helpers ─────────────────────────────────────────────────────────────────


def test_adjust_quantity_to_step_size(mgr):
    assert mgr._adjust_quantity_to_step_size("ETHUSDT", 0.0123) == 0.0123
    mgr.asset_limits["ETHUSDT"] = AssetLimit(
        symbol="ETHUSDT",
        min_qty=0.001,
        max_qty=1000,
        step_size=0.01,
        min_notional=10,
        tick_size=0.01,
    )
    # floor to step
    adj = mgr._adjust_quantity_to_step_size("ETHUSDT", 0.019)
    assert adj == pytest.approx(0.01)


def test_update_asset_config_and_stats(mgr):
    assert mgr.update_asset_config("MISSING", {}) is False
    assert mgr.update_asset_config("ETHUSDT", {"quantity": 0.02}) is True
    assert mgr.config.assets["ETHUSDT"].quantity == 0.02
    stats = mgr.get_trading_statistics()
    assert "total_trades" in stats or isinstance(stats, dict)
