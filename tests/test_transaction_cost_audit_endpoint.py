"""Endpoint POST /api/simulations/transaction-cost-audit (auditoría after-cost)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    key = "test-key-transaction-cost-audit"
    monkeypatch.setenv("API_KEY", key)
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/simulations/transaction-cost-audit",
        "/api/v1/commissions/transaction-cost-audit",
    ],
)
def test_transaction_cost_audit_401_without_auth(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("API_KEY", "audit-unauth-key")
    client = _client()
    response = client.post(
        path,
        json={
            "notional_quote": "1000",
            "side": "BUY",
            "order_type": "MARKET",
            "spread_bps": "0",
            "slippage_bps": "0",
        },
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/simulations/transaction-cost-audit",
        "/api/v1/commissions/transaction-cost-audit",
    ],
)
def test_transaction_cost_audit_200_and_friction_matches_components(
    auth_headers: dict[str, str], path: str
) -> None:
    client = _client()
    response = client.post(
        path,
        headers=auth_headers,
        json={
            "notional_quote": "1000",
            "side": "BUY",
            "order_type": "MARKET",
            "spread_bps": "5",
            "slippage_bps": "5",
            "commission_taker_fraction": "0.001",
            "commission_maker_fraction": "0.001",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    from decimal import Decimal

    comm = Decimal(data["commission_usdt"])
    spr = Decimal(data["spread_cost_usdt"])
    slip = Decimal(data["slippage_cost_usdt"])
    total = Decimal(data["total_friction_usdt"])
    assert total == comm + spr + slip


@pytest.mark.parametrize(
    "path",
    [
        "/api/simulations/transaction-cost-audit",
        "/api/v1/commissions/transaction-cost-audit",
    ],
)
def test_transaction_cost_audit_422_on_validation(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    key = "k-val-audit"
    monkeypatch.setenv("API_KEY", key)
    client = _client()
    response = client.post(
        path,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "notional_quote": "-1",
            "side": "BUY",
            "order_type": "MARKET",
        },
    )
    assert response.status_code == 422
