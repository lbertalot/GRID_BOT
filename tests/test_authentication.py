import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAuthentication:
    """Tests de autenticación con API_KEY"""
    
    def test_public_endpoints_no_auth_required(self):
        """Test de endpoints públicos que no requieren autenticación"""
        # Endpoint raíz
        response = client.get("/")
        assert response.status_code == 200
        
        # Endpoint de health check
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_protected_endpoints_without_auth(self):
        """Test de endpoints protegidos sin autenticación"""
        # Endpoints que requieren API_KEY
        protected_endpoints = [
            "/api/strategies",
            "/api/trade/execute",
            "/api/trade/backtest",
            "/api/trades"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} debería requerir autenticación"
    
    def test_protected_endpoints_with_valid_auth(self):
        """Test de endpoints protegidos con autenticación válida"""
        # API_KEY válida (debe coincidir con la del .env)
        valid_api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
        headers = {"Authorization": f"Bearer {valid_api_key}"}
        
        # Test endpoint de estrategias
        response = client.get("/api/strategies", headers=headers)
        assert response.status_code == 200, "Debería permitir acceso con API_KEY válida"
        
        # Test endpoint de trades
        response = client.get("/api/trades", headers=headers)
        assert response.status_code == 200, "Debería permitir acceso con API_KEY válida"
    
    def test_protected_endpoints_with_invalid_auth(self):
        """Test de endpoints protegidos con autenticación inválida"""
        # API_KEY inválida
        invalid_api_key = "invalid_key_123"
        headers = {"Authorization": f"Bearer {invalid_api_key}"}
        
        # Test endpoint de estrategias
        response = client.get("/api/strategies", headers=headers)
        assert response.status_code == 401, "Debería rechazar API_KEY inválida"
        
        # Test endpoint de trades
        response = client.get("/api/trades", headers=headers)
        assert response.status_code == 401, "Debería rechazar API_KEY inválida"
    
    def test_protected_endpoints_with_malformed_auth(self):
        """Test de endpoints protegidos con formato de autenticación incorrecto"""
        # Sin "Bearer"
        headers = {"Authorization": "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"}
        
        response = client.get("/api/strategies", headers=headers)
        assert response.status_code == 401, "Debería rechazar formato incorrecto"
        
        # Sin header Authorization
        response = client.get("/api/strategies")
        assert response.status_code == 401, "Debería rechazar sin header Authorization"
    
    def test_trade_execution_with_auth(self):
        """Test de ejecución de trade con autenticación"""
        valid_api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
        headers = {"Authorization": f"Bearer {valid_api_key}"}
        
        # Datos de prueba para trade
        trade_data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "strategy": "grid"
        }
        
        # Test sin autenticación
        response = client.post("/api/trade/execute", json=trade_data)
        assert response.status_code == 401, "Debería requerir autenticación"
        
        # Test con autenticación válida
        response = client.post("/api/trade/execute", json=trade_data, headers=headers)
        # Puede fallar por validación de datos, pero no por autenticación
        assert response.status_code != 401, "No debería fallar por autenticación"
    
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
            "initial_balance": 1000
        }
        
        # Test sin autenticación
        response = client.post("/api/trade/backtest", json=backtest_data)
        assert response.status_code == 401, "Debería requerir autenticación"
        
        # Test con autenticación válida
        response = client.post("/api/trade/backtest", json=backtest_data, headers=headers)
        # Puede fallar por validación de datos, pero no por autenticación
        assert response.status_code != 401, "No debería fallar por autenticación"

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 