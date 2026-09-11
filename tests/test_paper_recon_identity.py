"""Identidad Decimal |E − (cash + Σ qty·mid)| / E ≤ 0.1% con inventario abierto."""

from decimal import Decimal

from app.core.paper_equity_ledger import PaperCostModel, PaperEquityLedger

BTC = "BTCUSDT"
D = Decimal


def test_equity_identity_with_open_inventory_within_10bps():
    ledger = PaperEquityLedger(
        initial_cash=D("1000"),
        deployed_capital=D("1000"),
        cost_model=PaperCostModel(),
    )
    ledger.record_buy(BTC, D("0.01"), D("50000"), grid_level=0)
    mid = D("51234.56")
    breakdown = ledger.equity_breakdown({BTC: mid})
    qty = ledger.position(BTC)
    recomputed_inv = qty * mid
    equity = breakdown["equity"]
    cash = breakdown["cash"]
    identity = (cash + recomputed_inv - equity).copy_abs()
    ratio = identity / equity
    assert ratio <= D("0.001")
    assert breakdown["inventory_value"] == ledger.equity_breakdown({BTC: mid})["inventory_value"]
    assert cash + breakdown["inventory_value"] == equity
