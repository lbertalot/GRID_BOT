"""P0-A — IC-2 en el path ticker real (`compute_paper_portfolio_value`).

El path ops marca ticker, graba la serie y debe flatten IC-2 (DD ≥ 10% del
desplegado 200). Paper-only. Decimal. Sin wipe de telemetry. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.inventory_controls import (
    EVENT_IC2,
    IcControlsConfig,
    reset_inventory_control_guard,
)
from app.core.paper_equity_ledger import (
    MarkPriceUnavailable,
    PaperEquityLedger,
    PaperEquitySeries,
    compute_paper_portfolio_value,
)

D = Decimal
ETH = "ETHUSDT"
FLOOR = D("1826.92")
MID = D("1923.08")  # in-range
DEPLOYED = D("200")
PEAK = D("1000")
TARGET_EQUITY = D("979")  # DD 21 > 20 = 10% de 200


class FakeMarkPriceFeed:
    def __init__(self, prices):
        self.prices = {k: D(str(v)) for k, v in prices.items()}

    def get_price(self, symbol: str) -> Decimal:
        try:
            return self.prices[symbol]
        except KeyError as exc:
            raise MarkPriceUnavailable(symbol) from exc


@pytest.fixture
def _ic_guard():
    reset_inventory_control_guard(
        IcControlsConfig(
            enabled_ic1=True,
            enabled_ic2=True,
            symbol=ETH,
            range_floor=FLOOR,
            deployed_capital=DEPLOYED,
            ic2_threshold_pct=D("10.00"),
        )
    )
    yield
    reset_inventory_control_guard()


def _ledger_peak_1000_equity_979() -> tuple[PaperEquityLedger, PaperEquitySeries]:
    """Inventario ETH al cap 200; mid in-range; equity 979 vs pico 1000."""
    ledger = PaperEquityLedger(initial_cash=D("1000"), deployed_capital=DEPLOYED)
    series = PaperEquitySeries()
    series.record(PEAK)

    notional = DEPLOYED
    cost_mult = D("1.0012")  # 10 bps fee + 2 bps slippage
    cash_after = D("1000") - notional * cost_mult
    inv_needed = TARGET_EQUITY - cash_after
    qty = inv_needed / MID
    buy_px = notional / qty
    ledger.record_buy(ETH, qty, buy_px, grid_level=0)

    equity = ledger.mark_to_market({ETH: MID})
    assert equity == TARGET_EQUITY
    assert PEAK - equity > D("20")
    assert MID >= FLOOR
    return ledger, series


def test_compute_paper_portfolio_flattens_ic2_when_dd_exceeds_10pct_deployed(
    _ic_guard,
):
    from app.core.inventory_controls import get_inventory_control_guard

    ledger, series = _ledger_peak_1000_equity_979()
    qty_antes = ledger.position(ETH)
    assert qty_antes > D("0")

    payload = compute_paper_portfolio_value(
        ledger=ledger,
        price_feed=FakeMarkPriceFeed({ETH: str(MID)}),
        series=series,
    )

    assert payload is not None
    guard = get_inventory_control_guard()
    ic2_seen = any(e.get("event") == EVENT_IC2 for e in guard.state.last_events)
    flattened = ledger.position(ETH) < qty_antes
    assert ic2_seen or flattened or guard.state.flatten_pending
    assert flattened
    assert ledger.position(ETH) == D("0")
    assert guard.state.flatten_pending is False
    # A3: serie cierra con equity post-flatten (cash + inventario 0)
    last = series.samples[-1]
    assert D(last["equity"]) == ledger.cash
    assert D(last["inventory_value"]) == D("0")


def test_mark_price_unavailable_does_not_flatten_and_returns_none(_ic_guard):
    ledger, series = _ledger_peak_1000_equity_979()
    qty_antes = ledger.position(ETH)

    with patch(
        "app.core.inventory_controls.maybe_flatten_open_inventory_paper"
    ) as flatten:
        out = compute_paper_portfolio_value(
            ledger=ledger,
            price_feed=FakeMarkPriceFeed({}),
            series=series,
        )

    assert out is None
    flatten.assert_not_called()
    assert ledger.position(ETH) == qty_antes


def test_ic_exception_does_not_block_equity_payload(_ic_guard):
    ledger, series = _ledger_peak_1000_equity_979()
    expected = ledger.mark_to_market({ETH: MID})

    with patch(
        "app.core.inventory_controls.evaluate_and_enforce_from_paper",
        side_effect=RuntimeError("ic boom"),
    ):
        payload = compute_paper_portfolio_value(
            ledger=ledger,
            price_feed=FakeMarkPriceFeed({ETH: str(MID)}),
            series=series,
        )

    assert payload is not None
    assert payload["total_value_usdt"] == float(expected)
    assert ledger.position(ETH) > D("0")
