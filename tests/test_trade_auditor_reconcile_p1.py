"""P1: TradeAuditor auto-reconcile persiste cambios vía SessionLocal (mocks)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.trade_auditor import TradeAuditor
from app.models.trade import Trade


@pytest.fixture
def trade_auditor() -> TradeAuditor:
    return TradeAuditor()


def _mock_session_factory(mock_db: MagicMock):
    def factory():
        return mock_db

    return factory


@pytest.mark.asyncio
async def test_create_missing_internal_trade_inserts_row(
    trade_auditor: TradeAuditor,
) -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    discrepancy = {
        "type": "missing_internal",
        "order_id": 12345,
        "binance_trade": {
            "symbol": "ETHUSDT",
            "side": "BUY",
            "quantity": 0.1,
            "price": 3000.0,
            "timestamp": datetime(2026, 1, 1, 12, 0, 0),
            "order_id": 12345,
        },
    }

    with patch("app.core.trade_auditor.SessionLocal", _mock_session_factory(mock_db)):
        await trade_auditor._create_missing_internal_trade(discrepancy)

    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, Trade)
    assert added.order_id == "12345"
    assert added.symbol == "ETHUSDT"
    assert added.side == "BUY"
    assert added.quantity == 0.1
    assert added.entry_price == 3000.0
    assert added.strategy == "reconciled_from_binance"
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_create_missing_internal_trade_skips_when_exists(
    trade_auditor: TradeAuditor,
) -> None:
    mock_db = MagicMock()
    existing = Trade()
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    with patch("app.core.trade_auditor.SessionLocal", _mock_session_factory(mock_db)):
        await trade_auditor._create_missing_internal_trade(
            {
                "order_id": 99,
                "binance_trade": {
                    "symbol": "BTCUSDT",
                    "side": "SELL",
                    "quantity": 0.01,
                    "price": 50000.0,
                },
            }
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_update_trade_quantity_updates_row(trade_auditor: TradeAuditor) -> None:
    mock_db = MagicMock()
    row = Trade(
        symbol="ETHUSDT",
        side="BUY",
        quantity=0.1,
        entry_price=3000.0,
        order_id="67890",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = row

    with patch("app.core.trade_auditor.SessionLocal", _mock_session_factory(mock_db)):
        await trade_auditor._update_trade_quantity(
            {"order_id": 67890, "binance_value": 0.2}
        )

    assert row.quantity == 0.2
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_update_trade_price_updates_entry_price(
    trade_auditor: TradeAuditor,
) -> None:
    mock_db = MagicMock()
    row = Trade(
        symbol="ETHUSDT",
        side="BUY",
        quantity=0.1,
        entry_price=3000.0,
        order_id="111",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = row

    with patch("app.core.trade_auditor.SessionLocal", _mock_session_factory(mock_db)):
        await trade_auditor._update_trade_price(
            {"order_id": "111", "binance_value": 3010.5}
        )

    assert row.entry_price == 3010.5
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_auto_reconcile_runs_create_and_update(
    trade_auditor: TradeAuditor,
) -> None:
    mock_db = MagicMock()
    row = Trade(
        symbol="ETHUSDT",
        side="BUY",
        quantity=0.1,
        entry_price=3000.0,
        order_id="67890",
    )
    first_results = iter([None, row])

    def first_side_effect() -> Trade | None:
        return next(first_results)  # type: ignore[arg-type]

    mock_db.query.return_value.filter.return_value.first.side_effect = first_side_effect

    with patch("app.core.trade_auditor.SessionLocal", _mock_session_factory(mock_db)):
        result = await trade_auditor.auto_reconcile_discrepancies(
            [
                {
                    "type": "missing_internal",
                    "order_id": 12345,
                    "binance_trade": {
                        "symbol": "ETHUSDT",
                        "side": "BUY",
                        "quantity": 0.05,
                        "price": 3100.0,
                    },
                },
                {
                    "type": "quantity_mismatch",
                    "order_id": 67890,
                    "binance_value": 0.2,
                },
            ]
        )

    assert result["reconciled_count"] == 2
    assert result["failed_count"] == 0
    assert set(result["reconciled_orders"]) == {12345, 67890}
    assert row.quantity == 0.2


@pytest.mark.asyncio
async def test_compare_trades_matches_string_and_int_order_id(
    trade_auditor: TradeAuditor,
) -> None:
    internal = [
        {
            "id": 1,
            "symbol": "ETHUSDT",
            "side": "BUY",
            "quantity": 0.1,
            "price": 3000.0,
            "timestamp": datetime.now(),
            "profit_loss": 0.0,
            "order_id": "999",
        }
    ]
    binance = [
        {
            "id": 999,
            "symbol": "ETHUSDT",
            "side": "BUY",
            "quantity": 0.1,
            "price": 3000.0,
            "timestamp": datetime.now(),
            "order_id": 999,
            "commission": 0.0,
            "commission_asset": "USDT",
        }
    ]
    d = await trade_auditor._compare_trades(internal, binance)
    assert d == []
