import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0")

class TestAuthWorking:
    """Tests simples para verificar que la autenticación funciona"""
    
    def test_root_endpoint_works(self):
        r = requests.get(f"{BASE_URL}/", timeout=10)
        assert r.status_code == 200
        js = r.json()
        assert js.get("status") == "running"
    
    def test_price_endpoint_works(self):
        """Test del endpoint de precio"""
        r = requests.get(f"{BASE_URL}/api/trade/price/BTCUSDT", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "symbol" in data
        assert "price" in data
        assert data["symbol"] == "BTCUSDT"
        assert float(data["price"]) > 0
    
    def test_grid_config_get_works(self):
        """Test del endpoint GET de configuración de grid"""
        r = requests.get(f"{BASE_URL}/api/trade/grid_config", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict) and len(data) > 0
    
    def test_grid_config_post_with_auth(self):
        """Test del endpoint POST de configuración con autenticación válida"""
        headers = {"Authorization": f"Bearer {API_KEY}"}
        data = {
            "symbol": "BTCUSDT",
            "min_price": 25000,
            "max_price": 35000,
            "grids": 10,
            "quantity": 0.001
        }
        r = requests.post(f"{BASE_URL}/api/trade/grid_config", json=data, headers=headers, timeout=15)
        assert r.status_code in (200, 400)
        result = r.json()
        assert "message" in result
    
    def test_grid_config_post_without_auth(self):
        """Test del endpoint POST de configuración sin autenticación"""
        data = {
            "symbol": "BTCUSDT",
            "min_price": 25000,
            "max_price": 35000,
            "grids": 10,
            "quantity": 0.001
        }
        r = requests.post(f"{BASE_URL}/api/trade/grid_config", json=data, timeout=10)
        assert r.status_code in (401, 403)
    
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
        r = requests.post(f"{BASE_URL}/api/trade/grid_config", json=data, headers=headers, timeout=10)
        assert r.status_code in (401, 403)
    
    def test_order_endpoint_with_auth(self):
        """Test del endpoint de orden con autenticación válida"""
        headers = {"Authorization": f"Bearer {API_KEY}"}
        data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "type": "MARKET"
        }
        r = requests.post(f"{BASE_URL}/api/trade/order", json=data, headers=headers, timeout=20)
        assert r.status_code in (200, 400, 503)
    
    def test_order_endpoint_without_auth(self):
        """Test del endpoint de orden sin autenticación"""
        data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "type": "MARKET"
        }
        r = requests.post(f"{BASE_URL}/api/trade/order", json=data, timeout=10)
        assert r.status_code in (401, 403)
