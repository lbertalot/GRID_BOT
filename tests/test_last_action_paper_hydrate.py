"""TDD: last_action paper desde ledger (anti BUY-only)."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")


def test_resolve_last_action_from_ledger_buy(paper_env, monkeypatch):
    from app.core.paper_cycle_liquidity import resolve_last_grid_action

    fill = SimpleNamespace(symbol="ETHUSDT", side="BUY")
    ledger = MagicMock()
    ledger.fills = (fill,)
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: ledger,
    )
    assert resolve_last_grid_action("ETHUSDT") == "BUY"


def test_resolve_last_action_blocks_repeat_buy_in_decide(paper_env, monkeypatch):
    """Con last_action=BUY y last_level en L_i, precio en L_{i+1} → SELL (Δnivel≥1)."""
    from app.services.grid_strategy import decide_grid_action
    from app.core.paper_cycle_liquidity import resolve_last_grid_action

    fill = SimpleNamespace(symbol="ETHUSDT", side="BUY")
    ledger = MagicMock()
    ledger.fills = (fill,)
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.get_paper_ledger",
        lambda: ledger,
    )
    last = resolve_last_grid_action("ethusdt")
    levels = [1900.0, 1910.0, 1920.0]
    # Mismo nivel que el BUY → no SELL (evita RT intra-nivel)
    same = decide_grid_action(1909.0, levels, last_action=last, last_level=1910.0)
    assert same["action"] is None
    # Un nivel arriba → SELL
    action = decide_grid_action(1910.0, levels, last_action=last, last_level=1900.0)
    assert action["action"] == "SELL"
    action_mid = decide_grid_action(1910.0, levels, last_action=last, last_level=1900.0)
    assert action_mid["action"] == "SELL"


def test_resolve_last_action_fallback_when_not_paper(monkeypatch):
    from app.core.paper_cycle_liquidity import resolve_last_grid_action

    monkeypatch.setattr(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        lambda: False,
    )
    assert resolve_last_grid_action("ETHUSDT", fallback="SELL") == "SELL"
