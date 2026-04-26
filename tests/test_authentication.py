import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0")


class TestAuthentication:
    """Tests de autenticación con API_KEY"""

    def test_public_endpoints_no_auth_required(self):
        """Test de endpoints públicos que no requieren autenticación"""
        assert requests.get(f"{BASE_URL}/", timeout=10).status_code == 200
        assert requests.get(f"{BASE_URL}/health", timeout=10).status_code == 200

    def test_protected_endpoints_without_auth(self):
        """Test de endpoints protegidos sin autenticación"""
        # Endpoints que requieren API_KEY
        protected_endpoints = [
            "/api/strategies",
            "/api/trade/execute",
            "/api/trade/backtest",
            "/api/trades",
        ]

        for endpoint in protected_endpoints:
            r = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            assert r.status_code in (
                401,
                403,
            ), f"Endpoint {endpoint} debería requerir autenticación"

    def test_protected_endpoints_with_valid_auth(self):
        """Test de endpoints protegidos con autenticación válida"""
        # API_KEY válida (debe coincidir con la del .env)
        valid_api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
        headers = {"Authorization": f"Bearer {valid_api_key}"}

        # Test endpoint de estrategias
        r = requests.get(f"{BASE_URL}/api/strategies", headers=headers, timeout=10)
        assert r.status_code in (200, 404)

        # Test endpoint de trades
        r = requests.get(f"{BASE_URL}/api/trades", headers=headers, timeout=10)
        assert r.status_code in (200, 404)

    def test_protected_endpoints_with_invalid_auth(self):
        """Test de endpoints protegidos con autenticación inválida"""
        # API_KEY inválida
        invalid_api_key = "invalid_key_123"
        headers = {"Authorization": f"Bearer {invalid_api_key}"}

        # Test endpoint de estrategias
        r = requests.get(f"{BASE_URL}/api/strategies", headers=headers, timeout=10)
        assert r.status_code in (401, 403, 404)

        # Test endpoint de trades
        r = requests.get(f"{BASE_URL}/api/trades", headers=headers, timeout=10)
        assert r.status_code in (401, 403, 404)

    def test_protected_endpoints_with_malformed_auth(self):
        """Test de endpoints protegidos con formato de autenticación incorrecto"""
        # Sin "Bearer"
        headers = {"Authorization": "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"}
        response = requests.get(
            f"{BASE_URL}/api/strategies", headers=headers, timeout=10
        )
        assert response.status_code in (
            401,
            403,
            404,
        ), "Debería rechazar formato incorrecto"

        # Sin header Authorization
        response = requests.get(f"{BASE_URL}/api/strategies", timeout=10)
        assert response.status_code in (
            401,
            403,
            404,
        ), "Debería rechazar sin header Authorization"

    def test_trade_execution_with_auth(self):
        """Test de ejecución de trade con autenticación"""
        valid_api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
        headers = {"Authorization": f"Bearer {valid_api_key}"}

        # Datos de prueba para trade
        trade_data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "strategy": "grid",
        }

        # Test sin autenticación
        r = requests.post(f"{BASE_URL}/api/trade/execute", json=trade_data, timeout=10)
        assert r.status_code in (401, 403)

        # Test con autenticación válida
        r = requests.post(
            f"{BASE_URL}/api/trade/execute",
            json=trade_data,
            headers=headers,
            timeout=15,
        )
        assert r.status_code in (200, 400, 503)

    def test_backtest_with_auth(self):
        """Test de backtest con autenticación"""
        valid_api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
        headers = {"Authorization": f"Bearer {valid_api_key}"}

        # Datos de prueba para backtest
        backtest_data = {
            "symbol": "BTCUSDT",
            "strategy": "grid",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_balance": 1000,
        }

        # Test sin autenticación
        r = requests.post(
            f"{BASE_URL}/api/trade/backtest", json=backtest_data, timeout=10
        )
        assert r.status_code in (401, 403)

        # Test con autenticación válida
        r = requests.post(
            f"{BASE_URL}/api/trade/backtest",
            json=backtest_data,
            headers=headers,
            timeout=15,
        )
        assert r.status_code in (200, 400, 503)
