import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAuthWorking:
    """Tests simples para verificar que la autenticación funciona"""
    
    def test_root_endpoint_works(self):
        """Test del endpoint raíz"""
        response = client.get("/")
        assert response.status_code == 200
        assert "GridBot Web" in response.text
    
    def test_price_endpoint_works(self):
        """Test del endpoint de precio"""
        response = client.get("/api/trade/price/BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "price" in data
        assert data["symbol"] == "BTCUSDT"
        assert float(data["price"]) > 0
    
    def test_grid_config_get_works(self):
        """Test del endpoint GET de configuración de grid"""
        response = client.get("/api/trade/grid_config")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "min_price" in data
        assert "max_price" in data
        assert "grids" in data
    
    def test_grid_config_post_with_auth(self):
        """Test del endpoint POST de configuración con autenticación válida"""
        headers = {"Authorization": "Bearer aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"}
        data = {
            "symbol": "BTCUSDT",
            "min_price": 25000,
            "max_price": 35000,
            "grids": 10,
            "quantity": 0.001
        }
        response = client.post("/api/trade/grid_config", json=data, headers=headers)
        assert response.status_code == 200
        result = response.json()
        assert "message" in result
        assert result["message"] == "Configuración actualizada"
    
    def test_grid_config_post_without_auth(self):
        """Test del endpoint POST de configuración sin autenticación"""
        data = {
            "symbol": "BTCUSDT",
            "min_price": 25000,
            "max_price": 35000,
            "grids": 10,
            "quantity": 0.001
        }
        response = client.post("/api/trade/grid_config", json=data)
        assert response.status_code == 403  # Debería fallar sin autenticación
    
    def test_grid_config_post_with_invalid_auth(self):
        """Test del endpoint POST de configuración con autenticación inválida"""
        headers = {"Authorization": "Bearer invalid_key"}
        data = {
            "symbol": "BTCUSDT",
            "min_price": 25000,
            "max_price": 35000,
            "grids": 10,
            "quantity": 0.001
        }
        response = client.post("/api/trade/grid_config", json=data, headers=headers)
        assert response.status_code == 401  # Debería fallar con API_KEY inválida
    
    def test_order_endpoint_with_auth(self):
        """Test del endpoint de orden con autenticación válida"""
        headers = {"Authorization": "Bearer aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"}
        data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "type": "MARKET"
        }
        response = client.post("/api/trade/order", json=data, headers=headers)
        # Puede fallar por validación de datos, pero no por autenticación
        assert response.status_code != 403, "No debería fallar por autenticación"
    
    def test_order_endpoint_without_auth(self):
        """Test del endpoint de orden sin autenticación"""
        data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "type": "MARKET"
        }
        response = client.post("/api/trade/order", json=data)
        assert response.status_code == 403  # Debería fallar sin autenticación

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 