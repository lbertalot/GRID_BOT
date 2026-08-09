"""Smoke tests for S-COV-85 Wave 0.3 fixture pack (paper_env / mock_binance / Decimal)."""

from __future__ import annotations

from decimal import Decimal

from tests.fixtures.paper_cov import d


def test_decimal_helper_never_float():
    assert d("10.50") == Decimal("10.50")
    assert d(Decimal("1")) == Decimal("1")
    assert isinstance(d("0.0001"), Decimal)


def test_decimal_money_fixture(decimal_money):
    assert decimal_money("99.99") == Decimal("99.99")


def test_paper_env_defaults(paper_env, monkeypatch):
    import os

    assert os.getenv("PAPER_TRADING") == "true"
    assert os.getenv("FORCE_REAL_MODE") == ""
    assert os.getenv("TRADING_ENABLED") == "false"
    assert os.getenv("USE_REAL_BINANCE") == "0"
    assert os.getenv("EMERGENCY_STOP") == "true"


def test_mock_binance_blocks_create_order(mock_binance):
    from app.services.binance_client_singleton import get_binance_client_singleton

    singleton = get_binance_client_singleton()
    assert singleton is mock_binance
    check = singleton.validate_credentials_and_connectivity()
    assert check["ok"] is True
    try:
        singleton.client.create_order(symbol="BTCUSDT", side="BUY", type="MARKET")
        raised = False
    except AssertionError as exc:
        raised = True
        assert "create_order" in str(exc)
    assert raised
