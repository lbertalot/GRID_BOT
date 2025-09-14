import os
import pytest
import requests
import time

class TestMetrics:
    """Tests para verificar el sistema de métricas"""
    
    @pytest.fixture
    def api_base_url(self):
        return os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
    
    @pytest.fixture
    def auth_headers(self):
        api_key = os.getenv("API_KEY", "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0")
        return {"Authorization": f"Bearer {api_key}"}
    
    def test_metrics_health_endpoint(self, api_base_url, auth_headers):
        """Test del endpoint de health check de métricas"""
        response = requests.get(f"{api_base_url}/api/metrics/metrics/health", headers=auth_headers, timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "metrics_endpoints" in data
        
        print(f"✅ Health check de métricas funcionando")
        print(f"   Endpoints disponibles: {list(data['metrics_endpoints'].keys())}")
    
    def test_prometheus_metrics_endpoint(self, api_base_url):
        """Test del endpoint principal de métricas de Prometheus"""
        response = requests.get(f"{api_base_url}/api/metrics/metrics/", timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        content = response.text
        assert "# HELP gridbot_orders_total" in content
        assert "# HELP gridbot_volume_total" in content
        assert "# HELP gridbot_profit_loss" in content
        assert "# HELP gridbot_api_requests_total" in content
        
        print(f"✅ Endpoint de Prometheus funcionando")
        metric_count = len([line for line in content.split('\n') if 'gridbot_' in line])
        print(f"   Métricas disponibles: {metric_count}")
    
    def test_record_order_metrics(self, api_base_url, auth_headers):
        """Test para registrar métricas de órdenes"""
        # Registrar orden exitosa
        order_data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "strategy": "GRID",
            "quantity": 0.001,
            "price": 50000.0,
            "success": True
        }
        
        response = requests.post(f"{api_base_url}/api/metrics/metrics/record-order", headers=auth_headers, params=order_data, timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        # Registrar orden fallida
        failed_order_data = {
            "symbol": "ETHUSDT",
            "side": "SELL",
            "order_type": "LIMIT",
            "strategy": "SCALPING",
            "quantity": 0.01,
            "price": 3000.0,
            "success": False,
            "error_type": "INSUFFICIENT_BALANCE"
        }
        
        response = requests.post(f"{api_base_url}/api/metrics/metrics/record-order", headers=auth_headers, params=failed_order_data, timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        print(f"✅ Métricas de órdenes registradas correctamente")
    
    def test_update_balance_metrics(self, api_base_url, auth_headers):
        """Test para actualizar métricas de balance"""
        balance_data = {
            "asset": "USDT",
            "free": 1000.0,
            "locked": 50.0
        }
        
        response = requests.post(f"{api_base_url}/api/metrics/metrics/update-balance", headers=auth_headers, params=balance_data, timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        print(f"✅ Métricas de balance actualizadas correctamente")
    
    def test_update_strategy_metrics(self, api_base_url, auth_headers):
        """Test para actualizar métricas de estrategias"""
        strategy_data = {
            "strategy_type": "GRID",
            "active_count": 3
        }
        
        response = requests.post(f"{api_base_url}/api/metrics/metrics/update-strategy", headers=auth_headers, params=strategy_data, timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        print(f"✅ Métricas de estrategias actualizadas correctamente")
    
    def test_update_pnl_metrics(self, api_base_url, auth_headers):
        """Test para actualizar métricas de ganancias/pérdidas"""
        pnl_data = {
            "symbol": "BTCUSDT",
            "strategy": "GRID",
            "pnl": 25.50
        }
        
        response = requests.post(f"{api_base_url}/api/metrics/metrics/update-pnl", headers=auth_headers, params=pnl_data, timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        print(f"✅ Métricas de PnL actualizadas correctamente")
    
    def test_prometheus_target_status(self):
        """Test para verificar el estado de los targets de Prometheus"""
        response = requests.get(os.getenv("PROM_URL", "http://localhost:9090/api/v1/targets"), timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        data = response.json()
        targets = data["data"]["activeTargets"]
        
        # Verificar que el target principal esté funcionando
        gridbot_target = next((t for t in targets if t["labels"]["job"] == "gridbot-api"), None)
        
        assert gridbot_target is not None, "Target de GridBot no encontrado"
        assert gridbot_target["health"] == "up", f"Target de GridBot no está saludable: {gridbot_target['lastError']}"
        
        print(f"✅ Target de Prometheus funcionando correctamente")
        print(f"   Estado: {gridbot_target['health']}")
        print(f"   URL: {gridbot_target['scrapeUrl']}")
    
    def test_grafana_health(self):
        """Test para verificar el estado de Grafana"""
        response = requests.get(os.getenv("GRAFANA_URL", "http://localhost:3000/api/health"), timeout=10)
        
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        data = response.json()
        assert data["database"] == "ok"
        
        print(f"✅ Grafana funcionando correctamente")
        print(f"   Versión: {data['version']}")
        print(f"   Base de datos: {data['database']}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 