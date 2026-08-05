"""Tests unitarios para app/services/portfolio_snapshot_service.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# _compute_portfolio_value_sync — LD* asset handling
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _disable_paper_equity_sot():
    """Estos tests ejercitan el path Binance; en paper el ledger es SoT."""
    with patch(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        yield


def _make_binance_mock(balances, ticker_prices=None):
    """Construye un mock de cliente Binance con balances y tickers dados."""
    ticker_prices = ticker_prices or {}
    binance = MagicMock()
    binance.get_account.return_value = {"balances": balances}

    def get_ticker(symbol):
        if symbol in ticker_prices:
            return {"price": str(ticker_prices[symbol])}
        raise Exception(f"Invalid symbol {symbol}")

    binance.get_symbol_ticker = MagicMock(side_effect=lambda symbol: get_ticker(symbol))
    return binance


@patch("app.services.portfolio_snapshot_service.get_binance_client_singleton")
@patch("app.services.portfolio_snapshot_service.pipeline_filter_drops_total")
@patch(
    "app.services.portfolio_snapshot_service.portfolio_asset_valuation_failures_total"
)
def test_compute_ld_usdt_counts_as_usdt(mock_failures, mock_drops, mock_singleton):
    """LD*USDT assets deben sumarse al total USDT (Binance Earn)."""
    balances = [
        {"asset": "LDUSDT", "free": "100.0", "locked": "0.0"},
        {"asset": "USDT", "free": "200.0", "locked": "0.0"},
    ]
    binance = _make_binance_mock(balances)
    singleton = MagicMock()
    singleton.is_ready.return_value = True
    singleton.client = binance
    mock_singleton.return_value = singleton

    from app.services.portfolio_snapshot_service import _compute_portfolio_value_sync

    result = _compute_portfolio_value_sync()

    assert result is not None
    assert result["usdt_free"] == pytest.approx(300.0, rel=1e-6)
    assert result["total_value_usdt"] == pytest.approx(300.0, rel=1e-6)


@patch("app.services.portfolio_snapshot_service.get_binance_client_singleton")
@patch("app.services.portfolio_snapshot_service.pipeline_filter_drops_total")
@patch(
    "app.services.portfolio_snapshot_service.portfolio_asset_valuation_failures_total"
)
def test_compute_ld_btc_converts_at_price(mock_failures, mock_drops, mock_singleton):
    """LDBTC debe convertirse usando precio de BTCUSDT."""
    balances = [
        {"asset": "LDBTC", "free": "0.5", "locked": "0.0"},
    ]
    binance = _make_binance_mock(balances, ticker_prices={"BTCUSDT": 60000})
    singleton = MagicMock()
    singleton.is_ready.return_value = True
    singleton.client = binance
    mock_singleton.return_value = singleton

    from app.services.portfolio_snapshot_service import _compute_portfolio_value_sync

    result = _compute_portfolio_value_sync()

    assert result is not None
    assert result["btc_value_usdt"] == pytest.approx(30000.0, rel=1e-6)
    assert result["total_value_usdt"] == pytest.approx(30000.0, rel=1e-6)


@patch("app.services.portfolio_snapshot_service.get_binance_client_singleton")
@patch("app.services.portfolio_snapshot_service.pipeline_filter_drops_total")
@patch(
    "app.services.portfolio_snapshot_service.portfolio_asset_valuation_failures_total"
)
def test_compute_binance_not_ready_returns_none(
    mock_failures, mock_drops, mock_singleton
):
    """Si Binance no está ready, debe retornar None."""
    singleton = MagicMock()
    singleton.is_ready.return_value = False
    mock_singleton.return_value = singleton
    mock_drops.labels.return_value = MagicMock()

    from app.services.portfolio_snapshot_service import _compute_portfolio_value_sync

    result = _compute_portfolio_value_sync()

    assert result is None


@patch("app.services.portfolio_snapshot_service.get_binance_client_singleton")
@patch("app.services.portfolio_snapshot_service.pipeline_filter_drops_total")
@patch(
    "app.services.portfolio_snapshot_service.portfolio_asset_valuation_failures_total"
)
def test_compute_zero_balance_skipped(mock_failures, mock_drops, mock_singleton):
    """Balances con total=0 no deben valuarse ni sumarse."""
    balances = [
        {"asset": "BTC", "free": "0.0", "locked": "0.0"},
        {"asset": "USDT", "free": "500.0", "locked": "0.0"},
    ]
    binance = _make_binance_mock(balances)
    singleton = MagicMock()
    singleton.is_ready.return_value = True
    singleton.client = binance
    mock_singleton.return_value = singleton

    from app.services.portfolio_snapshot_service import _compute_portfolio_value_sync

    result = _compute_portfolio_value_sync()

    assert result["total_value_usdt"] == pytest.approx(500.0)
    assert result["btc_value_usdt"] == pytest.approx(0.0)


@patch("app.services.portfolio_snapshot_service.get_binance_client_singleton")
@patch("app.services.portfolio_snapshot_service.pipeline_filter_drops_total")
@patch(
    "app.services.portfolio_snapshot_service.portfolio_asset_valuation_failures_total"
)
def test_compute_stablecoins_counted_as_usdt(mock_failures, mock_drops, mock_singleton):
    """USDC, BUSD, FDUSD deben sumarse como USDT-equivalentes."""
    balances = [
        {"asset": "USDC", "free": "100.0", "locked": "0.0"},
        {"asset": "BUSD", "free": "50.0", "locked": "0.0"},
    ]
    binance = _make_binance_mock(balances)
    singleton = MagicMock()
    singleton.is_ready.return_value = True
    singleton.client = binance
    mock_singleton.return_value = singleton

    from app.services.portfolio_snapshot_service import _compute_portfolio_value_sync

    result = _compute_portfolio_value_sync()

    assert result["usdt_free"] == pytest.approx(150.0)
