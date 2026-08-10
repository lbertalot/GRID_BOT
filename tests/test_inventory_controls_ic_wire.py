"""E7 IC-WIRE — IC-1 freno fuera de rango + IC-2 flatten −10% desplegado.

TDD outline (desk-policy-l0 §2.5 / L0_PAPER_FREEZE_PARAMS §2):

1. IC-1: mid < range_floor → stop rebuy; BUY gate False; evento observable.
2. IC-1: mid vuelve ≥ floor → rebuy permitido (si armed y sin IC-2).
3. IC-2: DD desde pico ≥ 10% desplegado → flatten signal + desarme + evento.
4. Tras IC-2: cero BUY hasta rearm(reason).
5. Load freeze: ic_controls + min_price desde grid_config_paper_l0.json.
6. Decimal only; paper-only; sizing desplegado = 200.

Sin red / sin exchange.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.inventory_controls import (
    EVENT_IC1,
    EVENT_IC2,
    IcControlsConfig,
    InventoryControlGuard,
    InventoryControlInputError,
    evaluate_ic1_stop_rebuy,
    evaluate_ic2_flatten,
    load_ic_controls_from_grid_config,
    reset_inventory_control_guard,
)

D = Decimal
FLOOR = D("1826.92")  # −5% de mid freeze 1923.08
DEPLOYED = D("200")


@pytest.fixture(autouse=True)
def _reset_guard():
    reset_inventory_control_guard(
        IcControlsConfig(
            enabled_ic1=True,
            enabled_ic2=True,
            symbol="ETHUSDT",
            range_floor=FLOOR,
            deployed_capital=DEPLOYED,
            ic2_threshold_pct=D("10.00"),
        )
    )
    yield
    reset_inventory_control_guard()


# ---------------------------------------------------------------------------
# IC-1 — pure
# ---------------------------------------------------------------------------


def test_ic1_active_when_mid_below_range_floor():
    assert evaluate_ic1_stop_rebuy(mid=D("1800"), range_floor=FLOOR) is True


def test_ic1_inactive_when_mid_at_or_above_floor():
    assert evaluate_ic1_stop_rebuy(mid=FLOOR, range_floor=FLOOR) is False
    assert evaluate_ic1_stop_rebuy(mid=D("1900"), range_floor=FLOOR) is False


def test_ic1_rejects_non_positive():
    with pytest.raises(InventoryControlInputError):
        evaluate_ic1_stop_rebuy(mid=D("0"), range_floor=FLOOR)


# ---------------------------------------------------------------------------
# IC-2 — pure (mismo número que rojo MaxDD: 10% del desplegado)
# ---------------------------------------------------------------------------


def test_ic2_trips_at_10pct_deployed_dd():
    # peak 1000 → equity 980 = DD 20 = 10% de 200
    should, dd_pct = evaluate_ic2_flatten(
        equity_mtm=D("980"),
        peak_equity=D("1000"),
        deployed_capital=DEPLOYED,
        threshold_pct=D("10"),
    )
    assert should is True
    assert dd_pct == D("0.1")


def test_ic2_no_trip_below_threshold():
    # DD 19 USDT = 9.5% de 200
    should, dd_pct = evaluate_ic2_flatten(
        equity_mtm=D("981"),
        peak_equity=D("1000"),
        deployed_capital=DEPLOYED,
        threshold_pct=D("10"),
    )
    assert should is False
    assert dd_pct < D("0.1")


# ---------------------------------------------------------------------------
# Guard — eventos + enforce stub
# ---------------------------------------------------------------------------


def test_guard_ic1_blocks_buy_and_emits_event():
    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED)
    )
    decision = guard.observe(mid=D("1800"), equity_mtm=D("1000"), enforce=False)
    assert decision.ic1_active is True
    assert any(e["event"] == EVENT_IC1 and e.get("active") for e in decision.events)
    assert guard.allows_core_buy() is False


def test_guard_ic1_recovers_when_mid_back_in_range():
    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED)
    )
    guard.observe(mid=D("1800"), equity_mtm=D("1000"), enforce=False)
    decision = guard.observe(mid=D("1900"), equity_mtm=D("1000"), enforce=False)
    assert decision.ic1_active is False
    assert guard.allows_core_buy() is True
    assert any(e.get("recovered") for e in decision.events)


def test_guard_ic2_disarms_and_blocks_buy():
    trips: list[tuple[str, str]] = []

    def _breaker(btype: str, reason: str) -> None:
        trips.append((btype, reason))

    guard = InventoryControlGuard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED),
        activate_breaker=_breaker,
    )
    # Establece pico
    guard.observe(mid=D("1923"), equity_mtm=D("1000"), enforce=False)
    decision = guard.observe(mid=D("1923"), equity_mtm=D("980"), enforce=True)
    assert decision.ic2_should_flatten is True
    assert any(e["event"] == EVENT_IC2 for e in decision.events)
    assert guard.state.armed is False
    assert guard.allows_core_buy() is False
    assert trips == [("system_integrity", "IC2_flatten_core_at_deployed_dd")]


def test_guard_ic2_flatten_core_paper_sells_inventory():
    sold: list[dict] = []

    def _sell(*, symbol: str, quantity: Decimal, price: Decimal):
        sold.append(
            {"symbol": symbol, "quantity": quantity, "price": price}
        )
        return sold[-1]

    guard = InventoryControlGuard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED)
    )
    fills = guard.flatten_core_paper(
        positions={"ETHUSDT": D("0.1")},
        marks={"ETHUSDT": D("1800")},
        sell=_sell,
    )
    assert len(fills) == 1
    assert sold[0]["quantity"] == D("0.1")
    assert guard.state.armed is False
    assert guard.allows_core_buy() is False


def test_rearm_requires_reason():
    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED)
    )
    guard.observe(mid=D("1923"), equity_mtm=D("1000"), enforce=False)
    guard.observe(mid=D("1923"), equity_mtm=D("980"), enforce=True)
    with pytest.raises(InventoryControlInputError):
        guard.rearm(reason="")
    guard.rearm(reason="diagnóstico paper E7 — simulacro OK")
    assert guard.state.armed is True
    assert guard.allows_core_buy() is True


def test_guard_ic1_cancels_pending_buys_on_trip():
    from app.core.paper_pending_orders import (
        get_paper_pending_order_book,
        reset_paper_pending_order_book,
    )

    book = reset_paper_pending_order_book()
    book.add_buy(symbol="ETHUSDT", price=D("1800"), quantity=D("0.05"))
    book.add_buy(symbol="ETHUSDT", price=D("1790"), quantity=D("0.05"))
    assert len(book.list_open(side="BUY")) == 2

    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED)
    )
    decision = guard.observe(mid=D("1800"), equity_mtm=D("1000"), enforce=True)
    assert decision.ic1_active is True
    assert len(book.list_open(side="BUY")) == 0
    assert any(e.get("cancel_buys") for e in guard.state.last_events)


def test_guard_ic2_keeps_flatten_pending_until_maybe_flatten():
    from app.core.inventory_controls import maybe_flatten_open_inventory_paper

    sold: list[dict] = []

    def _sell(*, symbol: str, quantity: Decimal, price: Decimal):
        sold.append({"symbol": symbol, "quantity": quantity, "price": price})
        return sold[-1]

    guard = InventoryControlGuard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED),
        activate_breaker=lambda *_: None,
    )
    guard.observe(mid=D("1923"), equity_mtm=D("1000"), enforce=False)
    decision = guard.observe(mid=D("1923"), equity_mtm=D("980"), enforce=True)
    assert decision.ic2_should_flatten is True
    assert guard.state.flatten_pending is True
    assert guard.state.armed is False

    fills = maybe_flatten_open_inventory_paper(
        positions={"ETHUSDT": D("0.2")},
        marks={"ETHUSDT": D("1923")},
        sell=_sell,
        guard=guard,
    )
    assert len(fills) == 1
    assert sold[0]["quantity"] == D("0.2")
    assert guard.state.flatten_pending is False
    assert guard.allows_core_buy() is False


def test_maybe_flatten_noop_without_pending():
    from app.core.inventory_controls import maybe_flatten_open_inventory_paper

    guard = reset_inventory_control_guard(
        IcControlsConfig(range_floor=FLOOR, deployed_capital=DEPLOYED)
    )
    assert (
        maybe_flatten_open_inventory_paper(
            positions={"ETHUSDT": D("1")},
            marks={"ETHUSDT": D("1900")},
            sell=lambda **kw: kw,
            guard=guard,
        )
        == []
    )
    path = Path(__file__).resolve().parents[1] / "grid_config_paper_l0.json"
    if not path.is_file():
        pytest.skip("grid_config_paper_l0.json ausente")
    cfg = load_ic_controls_from_grid_config(path)
    assert cfg.enabled_ic1 is True
    assert cfg.ic2_threshold_pct == D("10.00")
    assert cfg.deployed_capital == D("200.00") or cfg.deployed_capital == D("200")
    assert cfg.symbol == "ETHUSDT"
    assert cfg.range_floor is not None
    assert cfg.range_floor == D(str(json.loads(path.read_text())["ETHUSDT"]["min_price"]))
