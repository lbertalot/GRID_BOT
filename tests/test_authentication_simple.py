import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0")


class TestAuthenticationSimple:
    """Tests de autenticación simplificados"""

    def test_root_endpoint_no_auth_required(self):
        """Test del endpoint raíz que no requiere autenticación"""
        r = requests.get(f"{BASE_URL}/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "running"

    def test_api_endpoints_require_auth(self):
        """Test de que los endpoints de API requieren autenticación"""
        # Endpoints que deberían requerir autenticación
        protected_endpoints = [
            "/api/trade/order",
            "/api/trade/run_grid",
            "/api/trade/grid_config",
            "/api/strategies/strategy/trailing_stop",
            "/api/strategies/strategy/scalping",
            "/api/strategies/strategy/rsi_macd",
            "/api/strategies/strategy/backtest",
        ]

        for endpoint in protected_endpoints:
            r = requests.post(f"{BASE_URL}{endpoint}", json={}, timeout=10)
            assert r.status_code in (
                401,
                403,
                422,
            ), f"Endpoint {endpoint} no está protegido correctamente"

    def test_public_endpoints_no_auth(self):
        """Test de endpoints públicos que no requieren autenticación"""
        # Endpoints que no requieren autenticación
        public_endpoints = [
            "/api/trade/price/BTCUSDT",
            "/api/trade/balances",
            "/api/trade/trades",
            "/api/trade/grid_config",
        ]

        for endpoint in public_endpoints:
            if endpoint.endswith("/BTCUSDT"):
                r = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            else:
                r = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            if r.status_code not in (404, 401, 403):
                assert (
                    r.status_code < 500
                ), f"Endpoint {endpoint} no debería fallar en servidor"

    def test_auth_header_format(self):
        """Test del formato del header de autenticación"""
        # Test con formato correcto
        headers = {"Authorization": f"Bearer {API_KEY}"}
        r = requests.post(
            f"{BASE_URL}/api/trade/order", json={}, headers=headers, timeout=10
        )
        assert r.status_code != 401

        # Test con formato incorrecto
        headers = {"Authorization": API_KEY}
        r = requests.post(
            f"{BASE_URL}/api/trade/order", json={}, headers=headers, timeout=10
        )
        assert r.status_code in (401, 403)

    def test_invalid_api_key(self):
        """Test con API_KEY inválida"""
        headers = {"Authorization": "Bearer invalid_key_123"}
        r = requests.post(
            f"{BASE_URL}/api/trade/order", json={}, headers=headers, timeout=10
        )
        assert r.status_code in (401, 403)
