import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAuthenticationSimple:
    """Tests de autenticación simplificados"""
    
    def test_root_endpoint_no_auth_required(self):
        """Test del endpoint raíz que no requiere autenticación"""
        response = client.get("/")
        assert response.status_code == 200
        assert "GridBot Web" in response.text
    
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
            "/api/strategies/strategy/backtest"
        ]
        
        for endpoint in protected_endpoints:
            response = client.post(endpoint, json={})
            # Debería devolver 401 (Unauthorized) o 422 (Validation Error)
            assert response.status_code in [401, 422], f"Endpoint {endpoint} no está protegido correctamente"
    
    def test_public_endpoints_no_auth(self):
        """Test de endpoints públicos que no requieren autenticación"""
        # Endpoints que no requieren autenticación
        public_endpoints = [
            "/api/trade/price/BTCUSDT",
            "/api/trade/balances",
            "/api/trade/trades",
            "/api/trade/grid_config"
        ]
        
        for endpoint in public_endpoints:
            if endpoint.endswith("/BTCUSDT"):
                response = client.get(endpoint)
            else:
                response = client.get(endpoint)
            # Estos endpoints pueden devolver 404 si no están configurados, pero no 401
            if response.status_code != 404:
                assert response.status_code != 401, f"Endpoint {endpoint} no debería requerir autenticación"
    
    def test_auth_header_format(self):
        """Test del formato del header de autenticación"""
        # Test con formato correcto
        headers = {"Authorization": "Bearer aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"}
        response = client.post("/api/trade/order", json={}, headers=headers)
        # Debería devolver 422 (Validation Error) pero no 401
        assert response.status_code != 401, "No debería fallar por autenticación con formato correcto"
        
        # Test con formato incorrecto
        headers = {"Authorization": "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"}
        response = client.post("/api/trade/order", json={}, headers=headers)
        assert response.status_code == 401, "Debería fallar con formato incorrecto"
    
    def test_invalid_api_key(self):
        """Test con API_KEY inválida"""
        headers = {"Authorization": "Bearer invalid_key_123"}
        response = client.post("/api/trade/order", json={}, headers=headers)
        assert response.status_code == 401, "Debería rechazar API_KEY inválida"

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 