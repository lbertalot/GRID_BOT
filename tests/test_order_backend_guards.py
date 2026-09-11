"""Fail-closed ticker / Postgres: no colocar orden. No muta breakers."""

from app.core.order_backend_guards import fail_closed_order_block
from app.core.paper_equity_ledger import PaperCostModel, PaperEquityLedger
from app.core.paper_trading import PaperTradingSystem


def test_guard_blocks_ticker_and_postgres():
    assert fail_closed_order_block(
        ticker_available=False, postgres_available=True
    ) == "fail_closed: ticker unavailable"
    assert fail_closed_order_block(
        ticker_available=True, postgres_available=False
    ) == "fail_closed: postgres unavailable"
    assert (
        fail_closed_order_block(ticker_available=True, postgres_available=True)
        is None
    )


def test_place_buy_rejected_when_ticker_down():
    engine = PaperTradingSystem(
        initial_balance=1000.0,
        ledger=PaperEquityLedger(
            initial_cash="1000",
            deployed_capital="200",
            cost_model=PaperCostModel(),
        ),
    )
    out = engine.place_buy_order(
        "BTCUSDT", 0.001, 50000, ticker_available=False
    )
    assert out["success"] is False
    assert "ticker" in out["error"]


def test_place_buy_rejected_when_postgres_down():
    engine = PaperTradingSystem(
        initial_balance=1000.0,
        ledger=PaperEquityLedger(
            initial_cash="1000",
            deployed_capital="200",
            cost_model=PaperCostModel(),
        ),
    )
    out = engine.place_buy_order(
        "BTCUSDT", 0.001, 50000, postgres_available=False
    )
    assert out["success"] is False
    assert "postgres" in out["error"]
