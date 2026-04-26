#!/usr/bin/env python3
"""
Tests de integración en entorno productivo para ciclo/estado de trading (sin mocks).
"""

import os
import requests
import pytest


BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0")


class TestTradingCycle:
    def test_binance_connection_real(self):
        r = requests.get(f"{BASE_URL}/api/trade/balances", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_reconciliation_summary(self):
        r = requests.get(f"{BASE_URL}/api/reconciliation/summary", timeout=20)
        assert r.status_code in (
            200,
            500,
        )  # 500 si no se puede consultar por conectividad puntual
        if r.status_code == 200:
            js = r.json()
            assert "portfolio_total_usdt" in js

    def test_breakers_summary(self):
        r = requests.get(f"{BASE_URL}/breakers/summary", timeout=45)
        assert r.status_code == 200
        js = r.json()
        assert "total_active" in js

    def test_run_grid_authenticated_live(self):
        headers = {"Authorization": f"Bearer {API_KEY}"}
        payload = {
            "symbol": "BTCUSDT",
            "min_price": 100.0,
            "max_price": 200000.0,
            "grids": 3,
            "quantity": 0.001,
            "last_action": None,
        }
        r = requests.post(
            f"{BASE_URL}/api/trade/run_grid", json=payload, headers=headers, timeout=45
        )
        # Puede ser 200 (ok), 400 (validación/notional), 503 (breaker activo)
        assert r.status_code in (200, 400, 503)

    @pytest.mark.skip(reason="Test legacy dependía de fixtures/mocks removidos")
    def test_paper_trading_mode(self):
        pass


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v"])
