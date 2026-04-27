"""Tests unitarios para app/services/pnl_service.py"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.pnl_service import settle_pnl_on_sell, recompute_profit_metrics, _d


# ──────────────────────────────────────────────────────────────────────────────
# _d helper
# ──────────────────────────────────────────────────────────────────────────────


def test_d_none_returns_zero():
    assert _d(None) == Decimal("0")


def test_d_decimal_passthrough():
    val = Decimal("12.34")
    assert _d(val) is val


def test_d_float_converts_correctly():
    result = _d(1.5)
    assert result == Decimal("1.5")
    assert isinstance(result, Decimal)


def test_d_string_converts():
    assert _d("99.99") == Decimal("99.99")


# ──────────────────────────────────────────────────────────────────────────────
# settle_pnl_on_sell
# ──────────────────────────────────────────────────────────────────────────────


def _mock_trade(
    symbol="BTCUSDT", side="BUY", qty="1.0", entry_price="50000", exit_price=None
):
    """Crea un trade mock con los atributos necesarios."""
    t = MagicMock()
    t.symbol = symbol
    t.side = side
    t.quantity = Decimal(qty)
    t.entry_price = Decimal(entry_price)
    t.exit_price = exit_price
    t.profit_loss = None
    t.timestamp = None
    return t


def _make_session(open_buys):
    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    order_mock = MagicMock()
    order_mock.all.return_value = open_buys
    filter_mock.order_by.return_value = order_mock
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


@patch("app.services.pnl_service.profit_total_usdt")
@patch("app.services.pnl_service.profit_by_asset_usdt")
@patch("app.services.pnl_service.roi_by_asset_percent")
def test_settle_pnl_full_close(mock_roi, mock_asset, mock_total):
    """SELL cierra exactamente un BUY abierto."""
    mock_total.labels.return_value = MagicMock()
    mock_asset.labels.return_value = MagicMock()
    mock_roi.labels.return_value = MagicMock()

    buy = _mock_trade(qty="1.0", entry_price="50000")
    db = _make_session([buy])

    result = settle_pnl_on_sell(db, "BTCUSDT", sell_qty="1.0", sell_price="55000")

    assert result["qty_closed"] == pytest.approx(1.0, rel=1e-6)
    assert result["pnl_realized"] == pytest.approx(5000.0, rel=1e-6)
    assert buy.exit_price == Decimal("55000")
    db.commit.assert_called_once()


@patch("app.services.pnl_service.profit_total_usdt")
@patch("app.services.pnl_service.profit_by_asset_usdt")
@patch("app.services.pnl_service.roi_by_asset_percent")
def test_settle_pnl_no_open_buys(mock_roi, mock_asset, mock_total):
    """Sin BUYs abiertos → PnL 0, qty_closed 0."""
    mock_total.labels.return_value = MagicMock()
    mock_asset.labels.return_value = MagicMock()
    mock_roi.labels.return_value = MagicMock()

    db = _make_session([])
    result = settle_pnl_on_sell(db, "BTCUSDT", sell_qty="1.0", sell_price="55000")

    assert result["pnl_realized"] == pytest.approx(0.0)
    assert result["qty_closed"] == pytest.approx(0.0)
    db.commit.assert_called_once()


@patch("app.services.pnl_service.profit_total_usdt")
@patch("app.services.pnl_service.profit_by_asset_usdt")
@patch("app.services.pnl_service.roi_by_asset_percent")
def test_settle_pnl_partial_close(mock_roi, mock_asset, mock_total):
    """SELL parcial: cierra parte del primer BUY."""
    mock_total.labels.return_value = MagicMock()
    mock_asset.labels.return_value = MagicMock()
    mock_roi.labels.return_value = MagicMock()

    buy = _mock_trade(qty="2.0", entry_price="50000")
    db = _make_session([buy])
    db.add = MagicMock()

    result = settle_pnl_on_sell(db, "BTCUSDT", sell_qty="1.0", sell_price="60000")

    assert result["qty_closed"] == pytest.approx(1.0, rel=1e-6)
    assert result["pnl_realized"] == pytest.approx(10000.0, rel=1e-6)
    # El buy original debe tener cantidad reducida a 1.0
    assert buy.quantity == Decimal("1.0")
    db.add.assert_called_once()


@patch("app.services.pnl_service.profit_total_usdt")
@patch("app.services.pnl_service.profit_by_asset_usdt")
@patch("app.services.pnl_service.roi_by_asset_percent")
def test_settle_pnl_negative_pnl(mock_roi, mock_asset, mock_total):
    """Venta a precio menor que compra → PnL negativo."""
    mock_total.labels.return_value = MagicMock()
    mock_asset.labels.return_value = MagicMock()
    mock_roi.labels.return_value = MagicMock()

    buy = _mock_trade(qty="1.0", entry_price="60000")
    db = _make_session([buy])

    result = settle_pnl_on_sell(db, "BTCUSDT", sell_qty="1.0", sell_price="55000")

    assert result["pnl_realized"] == pytest.approx(-5000.0, rel=1e-6)


# ──────────────────────────────────────────────────────────────────────────────
# recompute_profit_metrics
# ──────────────────────────────────────────────────────────────────────────────


@patch("app.services.pnl_service.profit_total_usdt")
@patch("app.services.pnl_service.profit_by_asset_usdt")
@patch("app.services.pnl_service.roi_by_asset_percent")
def test_recompute_profit_metrics_empty(mock_roi, mock_asset, mock_total):
    """Sin trades con profit_loss → set(0.0) correctamente."""
    mock_total.labels.return_value = MagicMock()
    mock_asset.labels.return_value = MagicMock()
    mock_roi.labels.return_value = MagicMock()

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    recompute_profit_metrics(db)

    mock_total.labels.return_value.set.assert_called_once_with(0.0)


@patch("app.services.pnl_service.profit_total_usdt")
@patch("app.services.pnl_service.profit_by_asset_usdt")
@patch("app.services.pnl_service.roi_by_asset_percent")
def test_recompute_profit_metrics_with_trades(mock_roi, mock_asset, mock_total):
    """Trades con profit_loss → métricas actualizadas correctamente."""
    mock_total.labels.return_value = MagicMock()
    mock_asset.labels.return_value = MagicMock()
    mock_roi.labels.return_value = MagicMock()

    t1 = MagicMock()
    t1.profit_loss = Decimal("100")
    t1.symbol = "BTCUSDT"
    t2 = MagicMock()
    t2.profit_loss = Decimal("-50")
    t2.symbol = "ETHUSDT"

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [t1, t2]

    recompute_profit_metrics(db)

    mock_total.labels.return_value.set.assert_called_once_with(pytest.approx(50.0))
