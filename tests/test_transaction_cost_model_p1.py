"""P1: modelo after-cost unificado (protocolo Passive Income §3.4)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.services.commission import CommissionRates
from app.services.transaction_cost_model import (
    TransactionCostAudit,
    compute_transaction_cost_audit,
)


def test_rejects_non_positive_notional() -> None:
    with pytest.raises(ValueError, match="positivo"):
        compute_transaction_cost_audit(
            Decimal("0"),
            "MARKET",
            "BUY",
            Decimal("1"),
            Decimal("1"),
        )


def test_buy_total_friction_increases_with_spread_and_slippage() -> None:
    base = compute_transaction_cost_audit(
        Decimal("1000"),
        "MARKET",
        "BUY",
        Decimal("0"),
        Decimal("0"),
    )
    with_extra = compute_transaction_cost_audit(
        Decimal("1000"),
        "MARKET",
        "BUY",
        Decimal("5"),
        Decimal("3"),
    )
    assert with_extra.total_friction_usdt > base.total_friction_usdt
    assert with_extra.spread_cost_usdt == Decimal("0.5")
    assert with_extra.slippage_cost_usdt == Decimal("0.3")


def test_sell_symmetric_friction_matches_buy_for_same_bps() -> None:
    buy = compute_transaction_cost_audit(
        Decimal("2000"), "MARKET", "BUY", Decimal("2"), Decimal("4")
    )
    sell = compute_transaction_cost_audit(
        Decimal("2000"), "MARKET", "SELL", Decimal("2"), Decimal("4")
    )
    assert buy.total_friction_usdt == sell.total_friction_usdt
    assert buy.spread_cost_usdt == sell.spread_cost_usdt


def test_commission_maker_vs_taker() -> None:
    rates = CommissionRates(
        maker=Decimal("0.0005"),
        taker=Decimal("0.001"),
    )
    maker_audit = compute_transaction_cost_audit(
        Decimal("5000"),
        "LIMIT",
        "BUY",
        Decimal("0"),
        Decimal("0"),
        commission_rates=rates,
    )
    taker_audit = compute_transaction_cost_audit(
        Decimal("5000"),
        "MARKET",
        "BUY",
        Decimal("0"),
        Decimal("0"),
        commission_rates=rates,
    )
    assert maker_audit.commission_usdt == Decimal("2.5")
    assert taker_audit.commission_usdt == Decimal("5")


def test_audit_to_dict_json_serializable() -> None:
    audit = compute_transaction_cost_audit(
        Decimal("100"),
        "MARKET",
        "SELL",
        Decimal("1"),
        Decimal("2"),
    )
    d = audit.to_serializable_dict()
    raw = json.dumps(d)
    assert "total_friction_usdt" in raw
    assert d["side"] == "SELL"
