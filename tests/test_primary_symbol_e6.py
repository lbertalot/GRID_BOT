"""E6 — portfolio_snapshots.primary_symbol → ETHUSDT en paper L0 / freeze."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.primary_symbol import resolve_primary_symbol


def test_resolve_primary_symbol_respects_trading_symbol(monkeypatch):
    monkeypatch.setenv("TRADING_SYMBOL", "BNBUSDT")
    assert resolve_primary_symbol() == "BNBUSDT"


def test_resolve_primary_symbol_paper_l0_defaults_eth(monkeypatch):
    monkeypatch.delenv("TRADING_SYMBOL", raising=False)
    monkeypatch.delenv("PRIMARY_SYMBOL", raising=False)
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.delenv("FORCE_REAL_MODE", raising=False)
    assert resolve_primary_symbol() == "ETHUSDT"


def test_compute_paper_portfolio_value_primary_symbol_eth(monkeypatch):
    monkeypatch.delenv("TRADING_SYMBOL", raising=False)
    monkeypatch.setenv("PAPER_TRADING", "true")

    from app.core.paper_equity_ledger import (
        PaperEquityLedger,
        PaperEquitySeries,
        compute_paper_portfolio_value,
    )

    ledger = PaperEquityLedger(
        initial_cash=Decimal("1000"),
        deployed_capital=Decimal("200"),
    )
    series = PaperEquitySeries()
    feed = MagicMock()
    feed.get_price.side_effect = lambda sym: Decimal("3500")

    payload = compute_paper_portfolio_value(
        ledger=ledger, price_feed=feed, series=series, record=False
    )
    assert payload is not None
    assert payload["primary_symbol"] == "ETHUSDT"


def test_live_path_snapshot_uses_resolver(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.delenv("TRADING_SYMBOL", raising=False)

    with patch(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.services.portfolio_snapshot_service.compute_paper_portfolio_value",
        return_value={
            "total_value_usdt": 1000.0,
            "usdt_free": 1000.0,
            "btc_value_usdt": 0.0,
            "other_assets_usdt": 0.0,
            "btc_price": None,
            "primary_symbol": resolve_primary_symbol(),
        },
    ):
        from app.services.portfolio_snapshot_service import _compute_portfolio_value_sync

        data = _compute_portfolio_value_sync()
        assert data["primary_symbol"] == "ETHUSDT"
