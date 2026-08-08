"""TDD: paper-iso liquidez en execute_trading_cycle (E-FILL-LIQ)."""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "false")


def test_paper_mode_prefers_ledger_cash_over_exchange_zero(paper_env, monkeypatch):
    from app.core import paper_cycle_liquidity as pcl

    ledger = MagicMock()
    ledger.cash = Decimal("1000")
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: ledger,
    )

    usdt, source = pcl.resolve_available_usdt_for_cycle(Decimal("0"))
    assert source == "paper_ledger"
    assert usdt == Decimal("1000")
    assert usdt >= Decimal("15")


def test_build_paper_balances_includes_usdt_and_base(paper_env, monkeypatch):
    from app.core.paper_cycle_liquidity import build_paper_balances_from_ledger

    ledger = MagicMock()
    ledger.cash = Decimal("1000")
    ledger.symbols.return_value = ["ETHUSDT"]
    ledger.position.return_value = Decimal("0")
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: ledger,
    )
    bal = build_paper_balances_from_ledger(symbols=["ETHUSDT"])
    assert bal["USDT"] == 1000.0
    assert "ETH" not in bal or bal.get("ETH", 0) == 0


def test_can_afford_buy_with_paper_usdt_without_base():
    from app.core.paper_cycle_liquidity import can_afford_grid_quantity

    ok = can_afford_grid_quantity(
        balances={"USDT": 1000.0},
        base_asset="ETH",
        quantity=0.003,
        price=3500.0,
        paper_mode=True,
    )
    assert ok is True
    no = can_afford_grid_quantity(
        balances={"USDT": 5.0},
        base_asset="ETH",
        quantity=0.003,
        price=3500.0,
        paper_mode=True,
    )
    assert no is False

def test_non_paper_uses_exchange_balance(monkeypatch):
    from app.core import paper_cycle_liquidity as pcl

    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: False,
    )

    usdt, source = pcl.resolve_available_usdt_for_cycle(Decimal("42.5"))
    assert source == "exchange"
    assert usdt == Decimal("42.5")


def test_skip_rebalancer_only_for_paper_ledger_source():
    from app.core.paper_cycle_liquidity import should_skip_exchange_rebalancer

    assert should_skip_exchange_rebalancer(liquidity_source="paper_ledger") is True
    assert should_skip_exchange_rebalancer(liquidity_source="exchange") is False


def test_execute_cycle_does_not_rebalance_when_paper_cash_ok(paper_env, monkeypatch):
    """Regresión: exchange USDT=0 + paper cash=1000 no debe skip por rebalancer."""
    from app.core.paper_cycle_liquidity import (
        resolve_available_usdt_for_cycle,
        should_skip_exchange_rebalancer,
    )

    ledger = MagicMock()
    ledger.cash = Decimal("1000.00")
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: ledger,
    )

    exchange_usdt = Decimal("0")
    available, source = resolve_available_usdt_for_cycle(exchange_usdt)
    assert available >= Decimal("15")
    # Con cash paper suficiente nunca entraría al branch de rebalancer.
    assert not (available < Decimal("15") and not should_skip_exchange_rebalancer(liquidity_source=source))
