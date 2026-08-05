"""S-PAPER-ISO (B27): CommissionManager no debe llamar get_account en paper."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("BINANCE_API_KEY", "k" * 64)
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s" * 64)


def test_commission_manager_skips_get_account_in_paper(paper_env, monkeypatch):
    mock_client_cls = MagicMock()
    mock_instance = MagicMock()
    mock_client_cls.return_value = mock_instance

    with patch("app.services.commission_manager.Client", mock_client_cls):
        # Re-import / construct fresh instance
        from app.services.commission_manager import CommissionManager

        mgr = CommissionManager()

    mock_client_cls.assert_not_called()
    mock_instance.get_account.assert_not_called()
    assert mgr.client is None
    # Defaults usable for paper fee model
    assert mgr.default_maker_commission == 0.001
    assert mgr.calculate_commission(100.0, "MARKET") == pytest.approx(0.1)


def test_commission_manager_may_fetch_when_not_paper(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("BINANCE_API_KEY", "k" * 64)
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s" * 64)

    mock_client_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.get_account.return_value = {
        "makerCommission": 10,
        "takerCommission": 10,
    }
    mock_client_cls.return_value = mock_instance

    with patch("app.services.commission_manager.Client", mock_client_cls):
        with patch("app.services.commission_manager.get_binance_proxies", return_value=None):
            from app.services.commission_manager import CommissionManager

            mgr = CommissionManager()

    mock_client_cls.assert_called_once()
    mock_instance.get_account.assert_called_once()
    assert mgr.default_maker_commission == pytest.approx(0.001)
