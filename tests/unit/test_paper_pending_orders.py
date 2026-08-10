"""TDD — paper pending BUY book (IC-A)."""

from __future__ import annotations

from decimal import Decimal

from app.core.paper_pending_orders import (
    cancel_pending_buys_paper,
    get_paper_pending_order_book,
    reset_paper_pending_order_book,
)


def test_add_list_cancel_buys():
    book = reset_paper_pending_order_book()
    o1 = book.add_buy(symbol="ethusdt", price="1800", quantity="0.1")
    o2 = book.add_buy(symbol="ETHUSDT", price="1790", quantity="0.05")
    assert o1.symbol == "ETHUSDT"
    assert len(book.list_open(side="BUY")) == 2
    canceled = cancel_pending_buys_paper(symbol="ETHUSDT", reason="test")
    assert len(canceled) == 2
    assert all(c["status"] == "CANCELED" for c in canceled)
    assert book.list_open(side="BUY") == []
    assert get_paper_pending_order_book() is book


def test_cancel_single_and_binance_shape():
    book = reset_paper_pending_order_book()
    o = book.add_buy(symbol="ETHUSDT", price=Decimal("1810"), quantity=Decimal("0.02"))
    raw = o.as_binance_dict()
    assert raw["side"] == "BUY" and raw["paper_only"] is True
    assert book.cancel(o.order_id) is not None
    assert book.cancel(o.order_id) is None  # already canceled
