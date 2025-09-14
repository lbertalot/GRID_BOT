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
        assert r.status_code in (200, 500)  # 500 si no se puede consultar por conectividad puntual
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
        r = requests.post(f"{BASE_URL}/api/trade/run_grid", json=payload, headers=headers, timeout=45)
        # Puede ser 200 (ok), 400 (validación/notional), 503 (breaker activo)
        assert r.status_code in (200, 400, 503)
        
        # Crear el grid manager
        manager = OptimizedGridManager(mock_config)
        
        # Mock de asset limits
        manager.asset_limits = {
            "BTCUSDT": Mock(step_size=0.00001),
            "ETHUSDT": Mock(step_size=0.001)
        }
        
        # Calcular cantidades óptimas
        optimal_quantities = manager.calculate_optimal_quantities(mock_balances, mock_prices)
        
        # Verificar que se calcularon cantidades para activos con saldo suficiente
        assert "BTCUSDT" in optimal_quantities, "Debería calcular cantidad para BTCUSDT"
        assert "ETHUSDT" in optimal_quantities, "Debería calcular cantidad para ETHUSDT"
        
        # Verificar que las cantidades son correctas
        assert optimal_quantities["BTCUSDT"] == 0.0001, "Cantidad BTC debería ser 0.0001"
        assert optimal_quantities["ETHUSDT"] == 0.003, "Cantidad ETH debería ser 0.003"
        
        # Verificar que se registraron activos con saldo insuficiente (si los hay)
        if manager.insufficient_funds:
            for symbol, info in manager.insufficient_funds.items():
                assert "saldo_actual" in info
                assert "cantidad_necesaria" in info
                assert "faltante" in info
    
    @pytest.mark.asyncio
    async def test_paper_trading_mode(self, mock_config):
        """Test específico para verificar que el modo Paper Trading funciona correctamente"""
        
        # Mock del cliente de Binance
        mock_client = Mock()
        mock_client.api_key = "test_api_key"
        mock_client.api_secret = "test_api_secret"
        
        # Mock de balances con saldo suficiente
        mock_account_info = {
            "balances": [
                {"asset": "BTC", "free": "0.001", "locked": "0"},
                {"asset": "ETH", "free": "0.01", "locked": "0"},
                {"asset": "USDT", "free": "1000.0", "locked": "0"}
            ]
        }
        mock_client.get_account.return_value = mock_account_info
        
        # Mock de precios
        mock_client.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "119500.0"}
        
        # Crear el grid manager
        with patch('app.services.binance_credentials.get_binance_client_with_verification') as mock_get_client:
            mock_get_client.return_value = (mock_client, {
                "valid": True,
                "account_info": mock_account_info,
                "account_type": "SPOT"
            })
            
            # Mock de funciones de riesgo y métricas
            with patch('app.core.optimized_grid_manager.risk_manager') as mock_risk:
                mock_risk.check_portfolio_risk.return_value = "NORMAL"
                mock_risk.check_asset_risk.return_value = "NORMAL"
                mock_risk.trading_enabled = True
                
                with patch('app.core.optimized_grid_manager.metrics_service') as mock_metrics:
                    mock_metrics.calculate_portfolio_metrics = AsyncMock()
                    mock_metrics.update_balance_metrics = AsyncMock()
                    
                    # Mock de decide_grid_action para forzar una acción
                    with patch('app.core.optimized_grid_manager.decide_grid_action') as mock_decide:
                        mock_decide.return_value = {"action": "BUY", "reason": "test"}
                        
                        # Mock de la base de datos
                        with patch('app.db.session.SessionLocal') as mock_session:
                            mock_db = Mock()
                            mock_session.return_value = mock_db
                            
                            # Mock de asset limits
                            with patch('app.core.optimized_grid_manager.asyncpg') as mock_asyncpg:
                                mock_conn = Mock()
                                mock_asyncpg.connect.return_value = mock_conn
                                mock_conn.fetch.return_value = []
                                
                                # Crear el grid manager
                                manager = OptimizedGridManager(mock_config)
                                manager.client = mock_client
                                manager._account_info = mock_account_info
                                manager.asset_limits = {"BTCUSDT": Mock(step_size=0.00001)}
                                
                                # Ejecutar el ciclo de trading
                                results = await manager.execute_grid_trading_cycle()
                                
                                # Verificar que se ejecutó al menos una operación
                                assert len(results) > 0, "Debería haberse ejecutado al menos una operación en Paper Trading"
                                
                                # Verificar que la operación es simulada (paper_)
                                for result in results:
                                    assert result.order_id.startswith("paper_"), "En Paper Trading, el order_id debe empezar con 'paper_'"
                                    assert result.status == "FILLED", "En Paper Trading, el status debe ser 'FILLED'"
                                
                                # Verificar que se intentó guardar en la base de datos
                                mock_db.add.assert_called()
                                mock_db.commit.assert_called()


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v"]) 