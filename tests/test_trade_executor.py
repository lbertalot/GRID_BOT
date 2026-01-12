"""
Tests para TradeExecutor - Bug #1 Fix
GridBot v2.5

Tests de integración para verificar que TradeExecutor:
1. Ejecuta órdenes correctamente
2. Actualiza balances con BalanceService
3. Guarda trades en DB
4. Maneja errores de concurrencia
"""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.trade_executor import TradeExecutor, get_trade_executor
from app.services.balance_service import BalanceService, ConcurrentModificationError


@pytest.fixture
def mock_binance_client():
    """Mock del cliente Binance"""
    client = Mock()
    client.create_order = Mock(return_value={
        'symbol': 'BTCUSDT',
        'orderId': 12345,
        'clientOrderId': 'test_order_123',
        'status': 'FILLED',
        'executedQty': '0.001',
        'cummulativeQuoteQty': '50.00',
        'fills': [{'price': '50000.00', 'qty': '0.001'}]
    })
    return client


@pytest.fixture
def mock_balance_service():
    """Mock del BalanceService"""
    balance_service = Mock(spec=BalanceService)
    balance_service.update_balance = asyncio.coroutine(lambda asset, amount: None)
    return balance_service


@pytest.fixture
def trade_executor(mock_binance_client, mock_balance_service):
    """TradeExecutor con mocks"""
    executor = TradeExecutor()
    executor.binance_client = mock_binance_client
    executor.balance_service = mock_balance_service
    return executor


class TestTradeExecutor:
    """Test suite para TradeExecutor"""
    
    def test_get_trade_executor_singleton(self):
        """Verificar que get_trade_executor retorna la misma instancia"""
        executor1 = get_trade_executor()
        executor2 = get_trade_executor()
        assert executor1 is executor2
    
    @pytest.mark.asyncio
    async def test_execute_market_buy_success(self, trade_executor, mock_binance_client, mock_balance_service):
        """Test: Ejecutar market buy exitosamente"""
        symbol = "BTCUSDT"
        quantity = Decimal("0.001")
        
        with patch('app.services.trade_executor.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Ejecutar
            result = await trade_executor.execute_market_buy(symbol, quantity)
            
            # Verificar llamada a Binance
            mock_binance_client.create_order.assert_called_once()
            
            # Verificar que se guardó en DB
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            
            # Verificar actualización de balances
            assert mock_balance_service.update_balance.call_count == 2  # -USDT, +BTC
            
            # Verificar resultado
            assert result['status'] == 'FILLED'
            assert result['symbol'] == 'BTCUSDT'
    
    @pytest.mark.asyncio
    async def test_execute_market_sell_success(self, trade_executor, mock_binance_client, mock_balance_service):
        """Test: Ejecutar market sell exitosamente"""
        symbol = "ETHUSDT"
        quantity = Decimal("0.01")
        
        mock_binance_client.create_order.return_value = {
            'symbol': 'ETHUSDT',
            'orderId': 67890,
            'clientOrderId': 'test_order_456',
            'status': 'FILLED',
            'executedQty': '0.01',
            'cummulativeQuoteQty': '30.00',
            'fills': [{'price': '3000.00', 'qty': '0.01'}]
        }
        
        with patch('app.services.trade_executor.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Ejecutar
            result = await trade_executor.execute_market_sell(symbol, quantity)
            
            # Verificar actualización de balances (inverso de buy)
            assert mock_balance_service.update_balance.call_count == 2  # +USDT, -ETH
            
            # Verificar resultado
            assert result['status'] == 'FILLED'
    
    @pytest.mark.asyncio
    async def test_execute_order_with_balance_conflict(self, trade_executor, mock_balance_service):
        """Test: Manejar conflicto de balance (optimistic locking)"""
        # Simular conflicto en actualización de balance
        mock_balance_service.update_balance.side_effect = ConcurrentModificationError(
            "Balance", "BTC", 1, 2
        )
        
        with patch('app.services.trade_executor.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Ejecutar - debería capturar la excepción
            result = await trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))
            
            # Verificar que se manejó el error
            # (no debería lanzar excepción, sino registrar en métricas)
            assert 'orderId' in result  # Orden se ejecutó
    
    @pytest.mark.asyncio
    async def test_execute_order_binance_error(self, trade_executor, mock_binance_client):
        """Test: Manejar error de Binance API"""
        # Simular error de Binance
        mock_binance_client.create_order.side_effect = Exception("Binance API Error")
        
        with patch('app.services.trade_executor.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Ejecutar - debería capturar la excepción
            result = await trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))
            
            # Verificar que no hay orderId (orden falló)
            assert result.get('orderId') is None or result == {}
    
    @pytest.mark.asyncio
    async def test_idempotency_with_client_order_id(self, trade_executor):
        """Test: Verificar que client_order_id se pasa correctamente"""
        client_order_id = "UNIQUE_ORDER_123"
        
        with patch('app.services.trade_executor.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Ejecutar con client_order_id
            await trade_executor.execute_market_buy(
                "BTCUSDT", 
                Decimal("0.001"), 
                client_order_id=client_order_id
            )
            
            # Verificar que se pasó el client_order_id
            call_kwargs = trade_executor.binance_client.create_order.call_args[1]
            assert call_kwargs.get('newClientOrderId') == client_order_id
    
    @pytest.mark.asyncio
    async def test_balance_updates_are_atomic(self, trade_executor, mock_balance_service):
        """Test: Verificar que updates de balance son atómicos"""
        update_calls = []
        
        async def track_updates(asset, amount):
            update_calls.append((asset, amount))
        
        mock_balance_service.update_balance.side_effect = track_updates
        
        with patch('app.services.trade_executor.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Ejecutar BUY
            await trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))
            
            # Verificar que ambos updates se llamaron en orden
            assert len(update_calls) == 2
            # Primero -USDT
            assert update_calls[0][0] == "USDT"
            assert update_calls[0][1] < 0
            # Luego +BTC
            assert update_calls[1][0] == "BTC"
            assert update_calls[1][1] > 0
    
    @pytest.mark.asyncio
    async def test_metrics_are_recorded(self, trade_executor):
        """Test: Verificar que las métricas se registran"""
        with patch('app.services.trade_executor.trade_execution_total') as mock_metric:
            with patch('app.services.trade_executor.SessionLocal') as mock_session:
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                
                # Ejecutar
                await trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))
                
                # Verificar que se incrementó el counter
                mock_metric.labels.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

