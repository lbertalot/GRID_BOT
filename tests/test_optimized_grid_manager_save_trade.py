"""
Regresión: _save_trade_to_db no debe fallar en SELL con BUY abierta (antes: trade indefinido).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.optimized_grid_manager import (
    OptimizedGridManager,
    GridManagerConfig,
    AssetConfig,
)


def _minimal_config() -> GridManagerConfig:
    assets = {
        "BTCUSDT": AssetConfig(
            symbol="BTCUSDT",
            min_price=10000.0,
            max_price=200000.0,
            grids=10,
            quantity=0.0001,
        ),
    }
    return GridManagerConfig(
        assets=assets, update_interval=60, min_notional_threshold=10.0
    )


@pytest.mark.asyncio
async def test_save_trade_sell_closes_open_buy_no_unbound_local():
    """SELL con BUY abierta: commit sobre la fila existente, sin referencia a trade nuevo."""
    mock_db = MagicMock()
    open_buy = MagicMock()
    open_buy.id = 42
    open_buy.entry_price = 100.0
    open_buy.quantity = 0.01
    open_buy.exit_price = None
    open_buy.profit_loss = None

    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = open_buy

    mgr = OptimizedGridManager(_minimal_config())

    with patch("app.db.session.SessionLocal", return_value=mock_db):
        await mgr._save_trade_to_db("BTCUSDT", "SELL", 0.01, 105.0, "oid-1")

    mock_db.commit.assert_called()
    assert open_buy.exit_price == 105.0
    assert open_buy.profit_loss is not None


@pytest.mark.asyncio
async def test_save_trade_sell_without_open_buy_inserts_row():
    """SELL sin BUY previa: insert de fila SELL (Trade real en query; no parchear Trade)."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    def refresh_side_effect(obj):
        obj.id = 99

    mock_db.refresh.side_effect = refresh_side_effect

    mgr = OptimizedGridManager(_minimal_config())

    with patch("app.db.session.SessionLocal", return_value=mock_db):
        await mgr._save_trade_to_db("BTCUSDT", "SELL", 0.01, 105.0, "oid-solo")

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_save_trade_invalid_skips_db():
    mgr = OptimizedGridManager(_minimal_config())
    with patch("app.db.session.SessionLocal") as SessionLocal:
        await mgr._save_trade_to_db("", "BUY", 0.01, 100.0, "x")
        SessionLocal.assert_not_called()

    with patch("app.db.session.SessionLocal") as SessionLocal:
        await mgr._save_trade_to_db("BTCUSDT", "BUY", -1, 100.0, "x")
        SessionLocal.assert_not_called()
