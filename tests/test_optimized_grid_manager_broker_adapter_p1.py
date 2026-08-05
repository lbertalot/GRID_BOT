"""P1: OptimizedGridManager SELL real vía ``place_spot_market_via_adapter`` (USE_BROKER_ADAPTER)."""

from __future__ import annotations

import importlib
import os
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _arm_real_order_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    def _allow(*, context: str = ""):
        return {"effective_mode": "real_armed", "context": context}

    import app.core.order_execution_guard as guard

    monkeypatch.setattr(guard, "assert_real_order_allowed", _allow)


def _reload_grid_manager():
    """
    ``tests/conftest.py`` sustituye globalmente ``_place_order`` por un fake
    paper-only; recargamos el módulo para ejecutar la implementación real en
    estos tests.
    """
    import app.core.optimized_grid_manager as ogm

    importlib.reload(ogm)
    return ogm


def _minimal_config(ogm):
    assets = {
        "BTCUSDT": ogm.AssetConfig(
            symbol="BTCUSDT",
            min_price=10000.0,
            max_price=200000.0,
            grids=10,
            quantity=0.0002,
        ),
    }
    return ogm.GridManagerConfig(
        assets=assets, update_interval=60, min_notional_threshold=10.0
    )


def _filled() -> Dict[str, Any]:
    return {
        "orderId": 77,
        "status": "FILLED",
        "symbol": "BTCUSDT",
        "side": "SELL",
        "fills": [{"price": "50000", "qty": "0.0002"}],
    }


@pytest.mark.asyncio
async def test_place_order_sell_real_uses_adapter_when_flag_on() -> None:
    ogm = _reload_grid_manager()
    OptimizedGridManager = ogm.OptimizedGridManager

    env_patch = {
        "PAPER_TRADING": "false",
        "USE_BROKER_ADAPTER": "true",
        "BROKER_PRIMARY_VENUE": "binance_spot",
    }

    mock_client = MagicMock()
    mock_client.api_key = "test-key"

    async def _adapter(**kwargs: Any) -> Dict[str, Any]:
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["side"] == "SELL"
        assert kwargs["binance_wrapper"] is not None
        return _filled()

    with patch.dict(os.environ, env_patch, clear=False):
        with patch.object(
            OptimizedGridManager, "_initialize_binance_client", return_value=mock_client
        ):
            mgr = OptimizedGridManager(_minimal_config(ogm))

    limits = MagicMock()
    limits.step_size = 0.00001
    mgr.asset_limits["BTCUSDT"] = limits

    with patch.dict(os.environ, env_patch, clear=False):
        with patch.object(
            mgr.async_binance, "get_price", new_callable=AsyncMock, return_value=50000.0
        ):
            with patch(
                "app.core.optimized_grid_manager.place_spot_market_via_adapter",
                new_callable=AsyncMock,
                side_effect=_adapter,
            ) as mock_place:
                assert ogm.os.getenv("PAPER_TRADING", "").lower() != "true"
                order = await mgr._place_order("BTCUSDT", "SELL", 0.0002)

    assert order is not None
    assert order.get("orderId") == 77
    mock_place.assert_awaited_once()
    mock_client.create_order.assert_not_called()


@pytest.mark.asyncio
async def test_place_order_sell_real_fallback_on_1021() -> None:
    ogm = _reload_grid_manager()
    OptimizedGridManager = ogm.OptimizedGridManager

    env_patch = {
        "PAPER_TRADING": "false",
        "USE_BROKER_ADAPTER": "true",
        "BROKER_PRIMARY_VENUE": "binance_spot",
    }

    mock_client = MagicMock()
    mock_client.api_key = "test-key"
    mock_client.create_order.return_value = _filled()

    with patch.dict(os.environ, env_patch, clear=False):
        with patch.object(
            OptimizedGridManager, "_initialize_binance_client", return_value=mock_client
        ):
            mgr = OptimizedGridManager(_minimal_config(ogm))

    limits = MagicMock()
    limits.step_size = 0.00001
    mgr.asset_limits["BTCUSDT"] = limits

    with patch.dict(os.environ, env_patch, clear=False):
        with patch.object(
            mgr.async_binance, "get_price", new_callable=AsyncMock, return_value=50000.0
        ):
            with patch(
                "app.core.optimized_grid_manager.place_spot_market_via_adapter",
                new_callable=AsyncMock,
                side_effect=Exception("timestamp -1021 drift"),
            ):
                order = await mgr._place_order("BTCUSDT", "SELL", 0.0002)

    assert order is not None
    mock_client.create_order.assert_called_once()
    call_kw = mock_client.create_order.call_args.kwargs
    assert call_kw["side"] == "SELL"
    assert call_kw["type"] == "MARKET"
