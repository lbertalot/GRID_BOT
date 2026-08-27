"""Contrato de visibilidad PAPER: ledger transaccional, marks y auth."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.paper_positions_routes import get_db
from app.core.metrics import (
    inventory_cap_usdt,
    inventory_cap_utilization_ratio,
    inventory_notional_usdt,
)
from app.main import app
from app.models.base import Base
from app.models.paper_ledger import PaperLedgerCycle
from app.services.paper_positions import PaperPositionUnavailable, read_paper_positions


@pytest.fixture
def memory_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.execute(
        text(
            "CREATE TABLE klines_data (symbol TEXT, close_price NUMERIC, open_time TIMESTAMP)"
        )
    )
    try:
        yield session
    finally:
        session.close()


def _cycle(symbol: str = "BTCUSDT") -> PaperLedgerCycle:
    return PaperLedgerCycle(
        cycle_id=f"{symbol}-cycle",
        symbol=symbol,
        buy_price=Decimal("60000"),
        buy_quantity=Decimal("0.0025"),
        open_quantity=Decimal("0.0025"),
        cost_basis_open_usdt=Decimal("150"),
        opened_at=datetime.now(timezone.utc),
    )


def test_paper_positions_are_valued_from_ledger_with_decimal_strings(memory_session):
    memory_session.add(_cycle())
    memory_session.commit()

    positions = read_paper_positions(
        memory_session, mark_provider=lambda _db, _symbols: {"BTCUSDT": Decimal("61000")}
    )

    assert positions[0].to_dict() == {
        "symbol": "BTCUSDT",
        "open_quantity": "0.0025",
        "cost_basis_open_usdt": "150",
        "mark_price": "61000",
        "market_value_usdt": "152.5",
        "unrealized_pnl_usdt": "2.5",
    }
    assert inventory_notional_usdt._value.get() == 150
    assert inventory_cap_usdt._value.get() == 200
    assert inventory_cap_utilization_ratio._value.get() == 0.75


def test_paper_positions_fail_closed_when_a_mark_is_missing(memory_session):
    memory_session.add(_cycle())
    memory_session.commit()

    with pytest.raises(PaperPositionUnavailable, match="mark.*BTCUSDT"):
        read_paper_positions(memory_session, mark_provider=lambda _db, _symbols: {})


def test_paper_positions_endpoint_requires_auth_and_returns_503_without_mark(
    memory_session, monkeypatch
):
    memory_session.add(_cycle())
    memory_session.commit()
    monkeypatch.setenv("API_KEY", "paper-visibility-key")
    app.dependency_overrides[get_db] = lambda: memory_session
    try:
        client = TestClient(app)
        assert client.get("/api/paper/positions").status_code == 401

        response = client.get(
            "/api/paper/positions",
            headers={"Authorization": "Bearer paper-visibility-key"},
        )
        assert response.status_code == 503
        assert "mark" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
