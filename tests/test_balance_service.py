"""Tests unitarios alineados con la API sync actual de BalanceService."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.balance import Balance
from app.services.balance_service import BalanceService, ConcurrentModificationError


def _mock_balance_query(db, balance_or_none):
    db.query.return_value.filter.return_value.first.return_value = balance_or_none


def test_update_balance_create_new():
    db = MagicMock()
    _mock_balance_query(db, None)
    created = BalanceService.update_balance(db, "ETH", Decimal("2.0"))
    assert created.asset == "ETH"
    assert created.amount == Decimal("2.0")
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_update_balance_existing_success():
    db = MagicMock()
    balance = Balance(asset="BTC", amount=Decimal("1.0"), version=1)
    _mock_balance_query(db, balance)
    db.execute.return_value.rowcount = 1
    updated = BalanceService.update_balance(db, "BTC", Decimal("0.5"))
    assert updated is balance
    db.execute.assert_called_once()
    db.commit.assert_called_once()


def test_update_balance_raises_after_max_retries():
    db = MagicMock()
    balance = Balance(asset="BTC", amount=Decimal("1.0"), version=1)
    _mock_balance_query(db, balance)
    db.execute.return_value.rowcount = 0  # fuerza conflicto CAS
    with patch("app.services.balance_service.time.sleep", return_value=None):
        with pytest.raises(ConcurrentModificationError):
            BalanceService.update_balance(db, "BTC", Decimal("0.5"), max_retries=3)
    assert db.execute.call_count == 3


def test_set_balance_existing_success():
    db = MagicMock()
    balance = Balance(asset="USDT", amount=Decimal("100.0"), version=2)
    _mock_balance_query(db, balance)
    db.execute.return_value.rowcount = 1
    result = BalanceService.set_balance(db, "USDT", Decimal("200.0"))
    assert result is balance
    db.execute.assert_called_once()
