"""Paper-safe fixtures for S-COV-85 Waves 0–3.

Opt-in fixtures (not autouse). Local fixtures with the same name in a test
module still override these via normal pytest scoping.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def d(value: Any) -> Decimal:
    """Money/qty helper — always Decimal, never float."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@pytest.fixture
def decimal_money():
    """Factory fixture: ``decimal_money("10.50")`` → ``Decimal("10.50")``."""
    return d


@pytest.fixture
def paper_env(monkeypatch):
    """Align env with CI paper-safe defaults (kill-switch on, no real Binance)."""
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("EMERGENCY_STOP", "true")
    return monkeypatch


@pytest.fixture
def mock_binance(monkeypatch):
    """Stub ``get_binance_client_singleton`` + credential check (no network)."""
    client = MagicMock(name="binance_client")
    client.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "50000.0"}
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "1000.00", "locked": "0.00"},
            {"asset": "BTC", "free": "0.01", "locked": "0.00"},
        ]
    }
    client.create_order.side_effect = AssertionError(
        "real create_order must not run under mock_binance / paper fixtures"
    )

    singleton = MagicMock(name="binance_client_singleton")
    singleton.client = client
    singleton.validate_credentials_and_connectivity = MagicMock(
        return_value={"ok": True, "mode": "paper_mock"}
    )
    singleton.validate_credentials = MagicMock(
        return_value={"ok": True, "mode": "paper_mock"}
    )
    # Async callers occasionally await helpers on the singleton.
    singleton.async_validate = AsyncMock(
        return_value={"ok": True, "mode": "paper_mock"}
    )

    monkeypatch.setattr(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        lambda: singleton,
        raising=False,
    )
    return singleton
