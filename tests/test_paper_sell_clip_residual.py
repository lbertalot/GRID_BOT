"""TDD Slice E-SELL-CLIP: SELL residual paper no queda trabado por piso 20.

Paper-only · Decimal · mocks ledger · sin Binance real · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.optimized_grid_manager import (
    AssetConfig,
    AssetLimit,
    GridManagerConfig,
    OptimizedGridManager,
    TradingResult,
)

pytestmark = [pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _ledger(position: Decimal) -> MagicMock:
    ledger = MagicMock()
    ledger.position.return_value = position
    ledger.cash = Decimal("990")
    return ledger


def test_clip_paper_sell_quantity_residual_position(paper_env, monkeypatch):
    """position 0.0053 vs sizer 0.0106 → clip a inventario (floor step 0.0001)."""
    from app.core.paper_cycle_liquidity import clip_paper_sell_quantity

    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: _ledger(Decimal("0.0053")),
    )

    clipped = clip_paper_sell_quantity(
        symbol="ETHUSDT",
        sizer_qty=Decimal("0.0106"),
        step_size=Decimal("0.0001"),
    )
    assert clipped == Decimal("0.0053")
    assert clipped < Decimal("0.0106")


def test_clip_paper_sell_quantity_zero_position(paper_env, monkeypatch):
    from app.core.paper_cycle_liquidity import clip_paper_sell_quantity

    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: _ledger(Decimal("0")),
    )

    clipped = clip_paper_sell_quantity(
        symbol="ETHUSDT",
        sizer_qty=Decimal("0.0106"),
        step_size=Decimal("0.0001"),
    )
    assert clipped == Decimal("0")


def test_clip_paper_sell_quantity_no_paper_sot_does_not_clip(monkeypatch):
    from app.core.paper_cycle_liquidity import clip_paper_sell_quantity

    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: _ledger(Decimal("0.0053")),
    )

    sizer = Decimal("0.0106")
    clipped = clip_paper_sell_quantity(
        symbol="ETHUSDT",
        sizer_qty=sizer,
        step_size=Decimal("0.0001"),
    )
    assert clipped == sizer


def test_should_not_enforce_level_notional_on_paper_sell():
    from app.core.paper_cycle_liquidity import should_enforce_level_notional_on_sell

    assert should_enforce_level_notional_on_sell(paper=True) is False
    assert should_enforce_level_notional_on_sell(paper=False) is True


def _mgr() -> OptimizedGridManager:
    cfg = GridManagerConfig(
        assets={
            "ETHUSDT": AssetConfig(
                symbol="ETHUSDT",
                min_price=1800.0,
                max_price=2200.0,
                grids=10,
                quantity=0.0106,
            )
        },
        update_interval=60,
        min_notional_threshold=20.0,
    )
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
        wrap.return_value.get_price = AsyncMock(return_value=1886.8)
        m = OptimizedGridManager(cfg)
        m.async_binance.get_price = AsyncMock(return_value=1886.8)
        m.asset_limits["ETHUSDT"] = AssetLimit(
            symbol="ETHUSDT",
            min_qty=0.0001,
            max_qty=100.0,
            step_size=0.0001,
            min_notional=10.0,
        )
        return m


@pytest.mark.anyio
async def test_paper_sell_residual_notional_10_not_dropped_by_threshold_20(
    paper_env, monkeypatch
):
    """SELL paper ~10 USDT no se descarta por min_notional_threshold=20."""
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: _ledger(Decimal("0.0053")),
    )

    mgr = _mgr()
    price = 1886.8
    residual_qty = 0.0053
    residual_notional = residual_qty * price
    assert residual_notional < 20
    assert residual_notional >= 10

    fm = MagicMock()
    fm.validate_trade_requirements = AsyncMock(
        return_value=(
            False,
            "Valor nocional insuficiente: $10.00 < $20.00",
            {
                "notional_value": residual_notional,
                "min_notional": 20.0,
                "min_quantity_required": 0.0106,
                "quantity": 0.0106,
            },
        )
    )
    trade = TradingResult(
        timestamp=datetime.now(),
        symbol="ETHUSDT",
        action="SELL",
        quantity=residual_qty,
        price=price,
        order_id="paper_residual_sell",
        status="FILLED",
    )
    exec_trade = AsyncMock(return_value=trade)

    with (
        patch.object(
            mgr,
            "get_asset_balances",
            AsyncMock(return_value={"USDT": 990.0, "ETH": 0.0053}),
        ),
        patch.object(
            mgr, "get_current_prices", AsyncMock(return_value={"ETHUSDT": price})
        ),
        patch(
            "app.core.optimized_grid_manager.strategy_manager.adapt_manager",
            AsyncMock(return_value=None),
        ),
        patch.object(
            mgr, "calculate_optimal_quantities", return_value={"ETHUSDT": 0.0106}
        ),
        patch(
            "app.core.paper_cycle_liquidity.resolve_last_grid_action",
            return_value="BUY",
        ),
        patch(
            "app.core.optimized_grid_manager.decide_grid_action",
            return_value={"action": "SELL", "level": 1},
        ),
        patch("app.services.fund_manager.fund_manager", fm),
        patch.object(mgr, "_execute_trade", exec_trade),
    ):
        results = await mgr.execute_grid_trading_cycle()

    assert len(results) == 1
    exec_trade.assert_awaited_once()
    sold_qty = Decimal(str(exec_trade.await_args.kwargs["quantity"]))
    assert sold_qty == Decimal("0.0053")
    assert sold_qty < Decimal("0.0106")
    assert exec_trade.await_args.kwargs["action"] == "SELL"
