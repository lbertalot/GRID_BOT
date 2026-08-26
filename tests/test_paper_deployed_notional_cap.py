"""TDD L0-A — el notional de inventario paper no puede superar deployed_capital.

Bug de mandato: `deployed_capital=200` era solo label (denominador MaxDD) mientras
`initial_cash=1000` operaba como wallet. El ledger real llegó a inventario ≈960 USDT.

Paper-only. Decimal. No wipe de telemetry. No live.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.paper_equity_ledger import (
    GridCycle,
    InsufficientPaperBalance,
    PaperDeployedCapitalExceeded,
    PaperEquityLedger,
)
from app.core.paper_trading import PaperTradingSystem

D = Decimal
ETH = "ETHUSDT"
DEPLOYED = D("200")


@pytest.fixture
def ledger() -> PaperEquityLedger:
    return PaperEquityLedger(initial_cash=D("1000"), deployed_capital=DEPLOYED)


def test_buy_dentro_del_desplegado_pasa(ledger):
    fill = ledger.record_buy(ETH, quantity=D("0.01"), price=D("1900"), grid_level=0)

    assert fill.notional_usdt == D("19")
    assert ledger.open_inventory_notional() == D("19")
    assert ledger.open_inventory_notional() <= ledger.deployed_capital


def test_buy_que_excede_deployed_200_falla_aunque_haya_cash(ledger):
    """Wallet 1000 no autoriza notional > 200. Gate de mandato, no de cash."""
    assert ledger.cash == D("1000")
    cash_antes = ledger.cash

    with pytest.raises(PaperDeployedCapitalExceeded) as exc:
        ledger.record_buy(ETH, quantity=D("0.11"), price=D("1900"), grid_level=0)

    assert "200" in str(exc.value)
    assert ledger.cash == cash_antes
    assert ledger.fills == ()
    assert ledger.open_inventory_notional() == D("0")


def test_buys_acumulados_no_superan_200(ledger):
    ledger.record_buy(ETH, quantity=D("0.05"), price=D("2000"), grid_level=0)  # 100
    ledger.record_buy(ETH, quantity=D("0.05"), price=D("2000"), grid_level=1)  # 100

    assert ledger.open_inventory_notional() == D("200")

    with pytest.raises(PaperDeployedCapitalExceeded):
        ledger.record_buy(ETH, quantity=D("0.01"), price=D("2000"), grid_level=2)

    assert ledger.open_inventory_notional() == D("200")
    assert len(ledger.fills) == 2


def test_sell_libera_cupo_sin_wipe(ledger):
    ledger.record_buy(ETH, quantity=D("0.10"), price=D("2000"), grid_level=0)  # 200
    ledger.record_sell(ETH, quantity=D("0.025"), price=D("2020"))  # libera 50

    assert ledger.open_inventory_notional() == D("150")
    fill = ledger.record_buy(ETH, quantity=D("0.025"), price=D("2000"), grid_level=1)
    assert fill.notional_usdt == D("50")
    assert ledger.open_inventory_notional() == D("200")


def test_inventario_ya_sobre_desplegado_bloquea_buy_sin_borrar_fills():
    """Estado tipo L0 actual (inv ≫ 200): no wipe; sí fail-closed en BUY nuevo."""
    ledger = PaperEquityLedger(initial_cash=D("1000"), deployed_capital=DEPLOYED)
    # Bypass del gate para reconstruir un ledger ya excedido (como el JSON de ops).
    ledger._cash = D("22.33")

    ledger._cycles.append(
        GridCycle(
            cycle_id="cyc-legacy-oversize",
            symbol=ETH,
            grid_level=0,
            buy_price=D("1900"),
            buy_quantity=D("0.50"),
            open_quantity=D("0.50"),
            buy_fee_usdt=D("0.95"),
            buy_slippage_usdt=D("0.19"),
            buy_fee_remaining=D("0.95"),
            buy_slippage_remaining=D("0.19"),
            opened_at=datetime(2026, 8, 10, 21, 12, 47, tzinfo=timezone.utc),
        )
    )
    assert ledger.open_inventory_notional() == D("950")
    fills_antes = len(ledger.fills)

    with pytest.raises(PaperDeployedCapitalExceeded):
        ledger.record_buy(ETH, quantity=D("0.0053"), price=D("1877.23"), grid_level=1)

    assert ledger.open_inventory_notional() == D("950")
    assert len(ledger.fills) == fills_antes
    # SELL sigue permitido: reduce inventario, no wipe.
    sell = ledger.record_sell(ETH, quantity=D("0.01"), price=D("1880"))
    assert sell.side == "SELL"
    assert ledger.open_inventory_notional() == D("931")


def test_cash_bajo_sigue_fallando_por_balance(ledger):
    ledger.record_buy(ETH, quantity=D("0.05"), price=D("2000"), grid_level=0)
    ledger._cash = D("5")
    with pytest.raises(InsufficientPaperBalance):
        ledger.record_buy(ETH, quantity=D("0.01"), price=D("1900"), grid_level=1)


def test_paper_trading_system_rechaza_buy_sobre_desplegado(tmp_path):
    ledger = PaperEquityLedger(
        initial_cash=D("1000"),
        deployed_capital=DEPLOYED,
        storage_path=tmp_path / "ledger.json",
    )
    pts = PaperTradingSystem(
        initial_balance=1000.0,
        state_file=str(tmp_path / "state.json"),
        ledger=ledger,
    )
    ok = pts.place_buy_order(ETH, 0.01, 1900.0, grid_level=0)
    assert ok["success"] is True
    denied = pts.place_buy_order(ETH, 0.10, 1900.0, grid_level=1)
    assert denied["success"] is False
    assert "deployed" in (denied.get("error") or "").lower() or "200" in (
        denied.get("error") or ""
    )
    assert ledger.open_inventory_notional() == D("19")


def test_open_inventory_notional_es_decimal(ledger):
    ledger.record_buy(ETH, quantity=D("0.01"), price=D("1915.02"), grid_level=0)
    value = ledger.open_inventory_notional()
    assert isinstance(value, Decimal)
    assert value == D("19.1502")
