"""COV-5.3 — main.py integrity POST + API aliases residual.

Paper-only · await directo (sin auth HTTP) · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def main_mod():
    import app.main as m

    return m


async def test_api_aliases_direct(main_mod):
    assert "trailing_stop" in (await main_mod.list_strategies(api_key="t"))[
        "strategies"
    ]
    assert (await main_mod.list_trades_alias(api_key="t"))["status"] == "ok"
    assert (await main_mod.execute_trade_alias(api_key="t"))["status"] == "ok"
    assert (await main_mod.backtest_trade_alias(api_key="t"))["status"] == "ok"
    assert (await main_mod.execute_trade_alias_get(api_key="t"))["status"] == "ok"
    assert (await main_mod.backtest_trade_alias_get(api_key="t"))["status"] == "ok"


async def test_force_balance_validation_ok_and_missing(main_mod):
    bv = MagicMock()
    bv.force_validation = AsyncMock()
    main_mod.balance_validator = bv

    out = await main_mod.force_balance_validation(api_key="t")
    assert "exitosamente" in out["message"]
    assert "timestamp" in out
    bv.force_validation.assert_awaited()

    main_mod.balance_validator = None
    with pytest.raises(HTTPException) as ei:
        await main_mod.force_balance_validation(api_key="t")
    # HTTPException(503) cae en except genérico → 500
    assert ei.value.status_code in (500, 503)


async def test_force_operation_check_ok_and_missing(main_mod):
    ot = MagicMock()
    ot.force_operation_check = AsyncMock()
    main_mod.operation_tracker = ot

    out = await main_mod.force_operation_check(api_key="t")
    assert "exitosamente" in out["message"]
    ot.force_operation_check.assert_awaited()

    main_mod.operation_tracker = None
    with pytest.raises(HTTPException) as ei:
        await main_mod.force_operation_check(api_key="t")
    assert ei.value.status_code in (500, 503)


async def test_update_binance_balance_success_and_fail(main_mod):
    bv = MagicMock()
    bv.update_real_binance_balance = AsyncMock(return_value=True)
    bv.force_balance_validation = AsyncMock(return_value={"ok": True})
    main_mod.balance_validator = bv

    ok = await main_mod.update_binance_balance(
        balance=1000.0, pnl=10.0, pnl_pct=1.0, api_key="t"
    )
    assert ok["status"] == "success"
    assert "1000" in ok["message"]

    bv.update_real_binance_balance = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as ei:
        await main_mod.update_binance_balance(balance=1.0, api_key="t")
    assert ei.value.status_code == 500

    main_mod.balance_validator = None
    with pytest.raises(HTTPException) as ei2:
        await main_mod.update_binance_balance(balance=1.0, api_key="t")
    assert ei2.value.status_code in (500, 503)


async def test_auto_correct_balance_success_and_fail(main_mod):
    bv = MagicMock()
    bv.auto_correct_balance_discrepancy = AsyncMock(
        return_value={"status": "success", "message": "ok"}
    )
    main_mod.balance_validator = bv

    ok = await main_mod.auto_correct_balance(api_key="t")
    assert ok["status"] == "success"
    assert "correction_details" in ok

    bv.auto_correct_balance_discrepancy = AsyncMock(
        return_value={"status": "error", "message": "nope"}
    )
    with pytest.raises(HTTPException) as ei:
        await main_mod.auto_correct_balance(api_key="t")
    assert ei.value.status_code == 500

    main_mod.balance_validator = None
    with pytest.raises(HTTPException) as ei2:
        await main_mod.auto_correct_balance(api_key="t")
    assert ei2.value.status_code in (500, 503)


async def test_get_integrity_status_degraded_and_critical(main_mod):
    bv = MagicMock()
    bv.last_validation = None
    ot = MagicMock()
    main_mod.balance_validator = bv
    main_mod.operation_tracker = ot
    main_mod.integrity_monitor = MagicMock()

    bv.get_validation_summary = AsyncMock(return_value={"integrity_score": 80})
    ot.get_operation_summary = AsyncMock(return_value={"success_rate": 0.8})
    deg = await main_mod.get_integrity_status()
    assert deg["status"] == "degraded"

    bv.get_validation_summary = AsyncMock(return_value={"integrity_score": 50})
    ot.get_operation_summary = AsyncMock(return_value={"success_rate": 0.5})
    crit = await main_mod.get_integrity_status()
    assert crit["status"] == "critical"


async def test_get_positions_delegates(main_mod):
    with patch(
        "app.main.get_portfolio_positions",
        new_callable=AsyncMock,
        return_value={"positions": []},
    ):
        out = await main_mod.get_positions(api_key="t")
    assert out == {"positions": []}


async def test_failed_and_partial_ops_when_tracker_missing(main_mod):
    main_mod.operation_tracker = None
    with pytest.raises(HTTPException) as e1:
        await main_mod.get_failed_operations()
    assert e1.value.status_code in (500, 503)

    with pytest.raises(HTTPException) as e2:
        await main_mod.get_partial_fills()
    assert e2.value.status_code in (500, 503)
