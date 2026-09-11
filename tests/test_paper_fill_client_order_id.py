"""TDD — client_order_id en PaperFill (fills nuevos). No wipe del ledger histórico."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.paper_equity_ledger import PaperCostModel, PaperEquityLedger, PaperFill


BTC = "BTCUSDT"
D = Decimal


@pytest.fixture
def ledger():
    return PaperEquityLedger(
        initial_cash=D("1000"),
        deployed_capital=D("200"),
        cost_model=PaperCostModel(),
    )


def test_from_dict_tolerates_missing_client_order_id():
    fill = PaperFill.from_dict(
        {
            "fill_id": "fil-old",
            "cycle_id": "cyc-old",
            "symbol": BTC,
            "side": "BUY",
            "quantity": "0.01",
            "price": "50000",
            "order_type": "LIMIT",
            "notional_usdt": "500",
            "commission": "0.1",
            "commission_asset": "USDT",
            "commission_usdt": "0.1",
            "slippage_usdt": "0.05",
            "grid_level": 0,
            "executed_at": datetime(2026, 8, 26, tzinfo=timezone.utc).isoformat(),
        }
    )
    assert fill.client_order_id == ""


def test_record_buy_persists_non_empty_client_order_id(ledger):
    fill = ledger.record_buy(
        BTC,
        D("0.001"),
        D("50000"),
        grid_level=0,
        client_order_id="paper-coid-abc",
    )
    assert fill.client_order_id == "paper-coid-abc"
    assert fill.to_dict()["client_order_id"] == "paper-coid-abc"


def test_record_buy_rejects_blank_client_order_id(ledger):
    with pytest.raises(ValueError, match="client_order_id"):
        ledger.record_buy(
            BTC, D("0.001"), D("50000"), grid_level=0, client_order_id="  "
        )


def test_record_buy_generates_id_when_omitted(ledger):
    fill = ledger.record_buy(BTC, D("0.001"), D("50000"), grid_level=0)
    assert fill.client_order_id.startswith("paper-")
