#!/usr/bin/env python3
"""
Test de integración para el ciclo de trading
Verifica que el sistema ejecute operaciones en modo paper trading
"""

import pytest
import asyncio
import os
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.core.optimized_grid_manager import (
    OptimizedGridManager, 
    GridManagerConfig, 
    AssetConfig,
    TradingResult
)
from app.services.binance_credentials import test_binance_connection


class TestTradingCycle:
    """Tests de integración para el ciclo de trading"""
    
    @pytest.fixture
    def mock_config(self):
        """Configuración de prueba con activos que tienen saldo suficiente"""
        return GridManagerConfig(
            assets={
                "BTCUSDT": AssetConfig(
                    symbol="BTCUSDT",
                    min_price=118000.0,
                    max_price=121000.0,
                    grids=4,
                    quantity=0.0001,
                    is_active=True
                ),
                "ETHUSDT": AssetConfig(
                    symbol="ETHUSDT",
                    min_price=3800.0,
                    max_price=3900.0,
                    grids=4,
                    quantity=0.003,
                    is_active=True
                )
            },
            update_interval=60,
            min_notional_threshold=10.0,
            max_concurrent_orders=3
        )
    
    @pytest.fixture
    def mock_balances(self):
        """Balances simulados con saldo suficiente"""
        return {
            "BTC": 0.001,  # Suficiente para 0.0001 BTC
            "ETH": 0.01,   # Suficiente para 0.003 ETH
            "USDT": 1000.0  # Saldo USDT disponible
        }
    
    @pytest.fixture
    def mock_prices(self):
        """Precios simulados dentro del rango de la grilla"""
        return {
            "BTCUSDT": 119500.0,  # Dentro del rango 118000-121000
            "ETHUSDT": 3850.0     # Dentro del rango 3800-3900
        }
    
    @pytest.mark.asyncio
    async def test_trading_cycle_with_sufficient_balance(self, mock_config, mock_balances, mock_prices):
        """Test que verifica que se ejecuten operaciones cuando hay saldo suficiente"""
        
        # Mock del cliente de Binance
        mock_client = Mock()
        mock_client.api_key = "test_api_key"
        mock_client.api_secret = "test_api_secret"
        
        # Mock de la función get_account para devolver balances
        mock_account_info = {
            "balances": [
                {"asset": "BTC", "free": "0.001", "locked": "0"},
                {"asset": "ETH", "free": "0.01", "locked": "0"},
                {"asset": "USDT", "free": "1000.0", "locked": "0"}
            ]
        }
        mock_client.get_account.return_value = mock_account_info
        
        # Mock de la función get_symbol_ticker para devolver precios
        def mock_get_symbol_ticker(symbol):
            return {"symbol": symbol, "price": str(mock_prices.get(symbol, 0))}
        
        mock_client.get_symbol_ticker.side_effect = mock_get_symbol_ticker
        
        # Mock de la función create_order para simular órdenes
        mock_client.create_order.return_value = {
            "orderId": "test_order_id",
            "status": "FILLED",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": "0.0001",
            "price": "119500.0"
        }
        
        # Crear el grid manager con el cliente mockeado
        with patch('app.services.binance_credentials.get_binance_client_with_verification') as mock_get_client:
            mock_get_client.return_value = (mock_client, {
                "valid": True,
                "account_info": mock_account_info,
                "account_type": "SPOT"
            })
            
            # Mock de las funciones de riesgo y métricas
            with patch('app.core.optimized_grid_manager.risk_manager') as mock_risk:
                mock_risk.check_portfolio_risk.return_value = "NORMAL"
                mock_risk.check_asset_risk.return_value = "NORMAL"
                mock_risk.trading_enabled = True
                
                with patch('app.core.optimized_grid_manager.metrics_service') as mock_metrics:
                    mock_metrics.calculate_portfolio_metrics = AsyncMock()
                    mock_metrics.update_balance_metrics = AsyncMock()
                    
                    # Mock de la función decide_grid_action para forzar una acción
                    with patch('app.core.optimized_grid_manager.decide_grid_action') as mock_decide:
                        mock_decide.return_value = {"action": "BUY", "reason": "test"}
                        
                        # Mock de la base de datos
                        with patch('app.db.session.SessionLocal') as mock_session:
                            mock_db = Mock()
                            mock_session.return_value = mock_db
                            
                            # Crear el grid manager
                            manager = OptimizedGridManager(mock_config)
                            manager.client = mock_client
                            manager._account_info = mock_account_info
                            
                            # Mock de asset limits
                            manager.asset_limits = {
                                "BTCUSDT": Mock(step_size=0.00001),
                                "ETHUSDT": Mock(step_size=0.001)
                            }
                            
                            # Ejecutar el ciclo de trading
                            results = await manager.execute_grid_trading_cycle()
                            
                            # Verificar que se ejecutaron operaciones
                            assert len(results) > 0, "Deberían haberse ejecutado operaciones"
                            
                            # Verificar que las operaciones tienen el formato correcto
                            for result in results:
                                assert isinstance(result, TradingResult)
                                assert result.symbol in ["BTCUSDT", "ETHUSDT"]
                                assert result.action in ["BUY", "SELL"]
                                assert result.quantity > 0
                                assert result.price > 0
                                assert result.order_id.startswith("paper_") or result.order_id == "test_order_id"
                                assert result.status == "FILLED"
                            
                            # Verificar que se intentó guardar en la base de datos
                            mock_db.add.assert_called()
                            mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_trading_cycle_insufficient_balance(self, mock_config):
        """Test que verifica que no se ejecuten operaciones cuando no hay saldo suficiente"""
        
        # Mock del cliente de Binance con saldo insuficiente
        mock_client = Mock()
        mock_client.api_key = "test_api_key"
        mock_client.api_secret = "test_api_secret"
        
        # Mock de la función get_account para devolver saldo insuficiente
        mock_account_info = {
            "balances": [
                {"asset": "BTC", "free": "0.00001", "locked": "0"},  # Insuficiente para 0.0001
                {"asset": "ETH", "free": "0.0001", "locked": "0"},   # Insuficiente para 0.003
                {"asset": "USDT", "free": "1000.0", "locked": "0"}
            ]
        }
        mock_client.get_account.return_value = mock_account_info
        
        # Mock de la función get_symbol_ticker
        mock_client.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "119500.0"}
        
        # Crear el grid manager con el cliente mockeado
        with patch('app.services.binance_credentials.get_binance_client_with_verification') as mock_get_client:
            mock_get_client.return_value = (mock_client, {
                "valid": True,
                "account_info": mock_account_info,
                "account_type": "SPOT"
            })
            
            # Mock de las funciones de riesgo
            with patch('app.core.optimized_grid_manager.risk_manager') as mock_risk:
                mock_risk.check_portfolio_risk.return_value = "NORMAL"
                mock_risk.check_asset_risk.return_value = "NORMAL"
                mock_risk.trading_enabled = True
                
                with patch('app.core.optimized_grid_manager.metrics_service') as mock_metrics:
                    mock_metrics.calculate_portfolio_metrics = AsyncMock()
                    mock_metrics.update_balance_metrics = AsyncMock()
                    
                    # Crear el grid manager
                    manager = OptimizedGridManager(mock_config)
                    manager.client = mock_client
                    manager._account_info = mock_account_info
                    
                    # Mock de asset limits
                    manager.asset_limits = {
                        "BTCUSDT": Mock(step_size=0.00001),
                        "ETHUSDT": Mock(step_size=0.001)
                    }
                    
                    # Ejecutar el ciclo de trading
                    results = await manager.execute_grid_trading_cycle()
                    
                    # Verificar que NO se ejecutaron operaciones
                    assert len(results) == 0, "No deberían haberse ejecutado operaciones con saldo insuficiente"
                    
                    # Verificar que se registraron los activos con saldo insuficiente
                    assert len(manager.insufficient_funds) > 0, "Deberían haberse registrado activos con saldo insuficiente"
    
    @pytest.mark.asyncio
    async def test_binance_credentials_validation(self):
        """Test que verifica que las credenciales de Binance sean válidas"""
        
        # Verificar que las credenciales estén configuradas
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        
        if not api_key or not api_secret:
            pytest.skip("Credenciales de Binance no configuradas para testing")
        
        # Verificar conexión con Binance
        connection_valid = test_binance_connection()
        assert connection_valid, "Las credenciales de Binance deberían ser válidas"
    
    def test_calculate_optimal_quantities(self, mock_config, mock_balances, mock_prices):
        """Test que verifica el cálculo de cantidades óptimas"""
        
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