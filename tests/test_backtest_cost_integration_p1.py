"""P1: integración costos de transacción ↔ parámetros vectorbt en BacktestingService."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.backtesting_service import BacktestConfig, BacktestingService
from app.services.transaction_cost_model import (
    build_reference_transaction_cost_audit,
    vectorbt_fees_and_slippage_from_backtest_fractions,
)


def test_vectorbt_mapping_backward_compatible_when_spread_zero() -> None:
    f, s = vectorbt_fees_and_slippage_from_backtest_fractions(0.001, 0.0005, 0.0)
    assert f == 0.001
    assert s == 0.0005


def test_vectorbt_mapping_adds_spread_to_slippage() -> None:
    f, s = vectorbt_fees_and_slippage_from_backtest_fractions(0.001, 0.0005, 10.0)
    assert f == 0.001
    assert s == pytest.approx(0.0005 + 0.001)


def test_vectorbt_mapping_rejects_negative_spread() -> None:
    with pytest.raises(ValueError, match="spread_bps"):
        vectorbt_fees_and_slippage_from_backtest_fractions(0.001, 0.0, -1.0)


def test_reference_audit_total_matches_components() -> None:
    audit = build_reference_transaction_cost_audit(
        Decimal("1000"),
        commission_fraction=0.001,
        slippage_fraction=0.0005,
        spread_bps=5.0,
        order_type="MARKET",
    )
    expected = audit.commission_usdt + audit.spread_cost_usdt + audit.slippage_cost_usdt
    assert audit.total_friction_usdt == expected


def test_backtest_config_validates_order_type() -> None:
    with pytest.raises(ValueError):
        BacktestConfig(backtest_order_type="STOP")

    cfg = BacktestConfig(backtest_order_type="limit")
    assert cfg.backtest_order_type == "LIMIT"


def test_backtesting_service_vectorbt_tuple_uses_config() -> None:
    svc = BacktestingService(results_dir="/tmp/gridbot_backtest_test")
    cfg = BacktestConfig(
        spread_bps=8.0,
        commission=0.002,
        slippage=0.0001,
    )
    f, s = svc._vectorbt_fees_slippage(cfg)
    assert f == 0.002
    assert s == pytest.approx(0.0001 + 0.0008)
