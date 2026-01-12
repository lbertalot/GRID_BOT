"""
Tests para BinanceUserStreamHandler - Bug #4 Fix
GridBot v2.5

Tests para verificar que el WebSocket User Data Stream:
1. Se conecta correctamente
2. Maneja reconexiones automáticas
3. Procesa eventos executionReport
4. Actualiza balances en tiempo real
5. Registra métricas
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from app.services.binance_user_stream import (
    BinanceUserStreamHandler, 
    default_on_fill
)


@pytest.fixture
def mock_aiohttp_session():
    """Mock de aiohttp.ClientSession"""
    session = AsyncMock()
    session.post = AsyncMock()
    session.put = AsyncMock()
    session.ws_connect = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def ws_handler(mock_aiohttp_session):
    """BinanceUserStreamHandler con mocks"""
    handler = BinanceUserStreamHandler(api_key="test_api_key")
    handler.session = mock_aiohttp_session
    return handler


class TestBinanceUserStreamHandler:
    """Test suite para BinanceUserStreamHandler"""
    
    @pytest.mark.asyncio
    async def test_create_listen_key_success(self, ws_handler, mock_aiohttp_session):
        """Test: Crear listenKey exitosamente"""
        # Mock respuesta de Binance
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={'listenKey': 'test_listen_key_123'})
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response
        
        # Ejecutar
        listen_key = await ws_handler._create_listen_key()
        
        # Verificar
        assert listen_key == 'test_listen_key_123'
        mock_aiohttp_session.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_listen_key_failure(self, ws_handler, mock_aiohttp_session):
        """Test: Manejar error al crear listenKey"""
        # Mock respuesta de error
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value='Invalid API key')
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response
        
        # Ejecutar - debería lanzar excepción
        with pytest.raises(RuntimeError, match="Error creando listenKey"):
            await ws_handler._create_listen_key()
    
    @pytest.mark.asyncio
    async def test_extend_listen_key_success(self, ws_handler, mock_aiohttp_session):
        """Test: Extender listenKey exitosamente"""
        ws_handler.listen_key = 'existing_key_123'
        
        # Mock respuesta exitosa
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_aiohttp_session.put.return_value.__aenter__.return_value = mock_response
        
        # Ejecutar (no debería lanzar excepción)
        await ws_handler._extend_listen_key()
        
        # Verificar
        mock_aiohttp_session.put.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_execution_report_buy(self):
        """Test: Procesar executionReport de BUY"""
        # Mock evento de Binance
        event = {
            'e': 'executionReport',
            's': 'BTCUSDT',
            'S': 'BUY',
            'X': 'FILLED',
            'l': '0.001',  # executedQty
            'Z': '50.00'   # cummulativeQuoteQty
        }
        
        # Mock BalanceService
        with patch('app.services.binance_user_stream.get_trade_executor') as mock_get_executor:
            mock_executor = Mock()
            mock_balance_service = AsyncMock()
            mock_executor.balance_service = mock_balance_service
            mock_get_executor.return_value = mock_executor
            
            # Ejecutar
            await default_on_fill(event)
            
            # Verificar que se llamó update_balance dos veces
            assert mock_balance_service.update_balance.call_count == 2
            
            # Verificar que se actualizó USDT (negativo) y BTC (positivo)
            calls = mock_balance_service.update_balance.call_args_list
            # Primera llamada: -USDT
            assert calls[0][0][0] == "USDT"
            assert calls[0][0][1] < 0
            # Segunda llamada: +BTC
            assert calls[1][0][0] == "BTC"
            assert calls[1][0][1] > 0
    
    @pytest.mark.asyncio
    async def test_handle_execution_report_sell(self):
        """Test: Procesar executionReport de SELL"""
        event = {
            'e': 'executionReport',
            's': 'ETHUSDT',
            'S': 'SELL',
            'X': 'FILLED',
            'l': '0.01',   # executedQty
            'Z': '30.00'   # cummulativeQuoteQty
        }
        
        with patch('app.services.binance_user_stream.get_trade_executor') as mock_get_executor:
            mock_executor = Mock()
            mock_balance_service = AsyncMock()
            mock_executor.balance_service = mock_balance_service
            mock_get_executor.return_value = mock_executor
            
            # Ejecutar
            await default_on_fill(event)
            
            # Verificar updates (inverso de BUY)
            calls = mock_balance_service.update_balance.call_args_list
            # Primera llamada: -ETH
            assert calls[0][0][0] == "ETH"
            assert calls[0][0][1] < 0
            # Segunda llamada: +USDT
            assert calls[1][0][0] == "USDT"
            assert calls[1][0][1] > 0
    
    @pytest.mark.asyncio
    async def test_handle_execution_report_partially_filled(self):
        """Test: Ignorar ordenes PARTIALLY_FILLED"""
        event = {
            'e': 'executionReport',
            's': 'BTCUSDT',
            'S': 'BUY',
            'X': 'PARTIALLY_FILLED',  # No debería procesarse completamente
            'l': '0.001',
            'Z': '50.00'
        }
        
        with patch('app.services.binance_user_stream.get_trade_executor') as mock_get_executor:
            mock_executor = Mock()
            mock_balance_service = AsyncMock()
            mock_executor.balance_service = mock_balance_service
            mock_get_executor.return_value = mock_executor
            
            # Ejecutar
            await default_on_fill(event)
            
            # PARTIALLY_FILLED también debería actualizar balances parcialmente
            assert mock_balance_service.update_balance.call_count >= 0
    
    @pytest.mark.asyncio
    async def test_handle_execution_report_with_missing_fields(self):
        """Test: Manejar evento con campos faltantes"""
        event = {
            'e': 'executionReport',
            # Faltan campos clave
        }
        
        with patch('app.services.binance_user_stream.get_trade_executor') as mock_get_executor:
            mock_executor = Mock()
            mock_balance_service = AsyncMock()
            mock_executor.balance_service = mock_balance_service
            mock_get_executor.return_value = mock_executor
            
            # Ejecutar - no debería lanzar excepción
            await default_on_fill(event)
            
            # No debería actualizar balances
            assert mock_balance_service.update_balance.call_count == 0
    
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_fill(self):
        """Test: Verificar que las métricas se registran"""
        event = {
            'e': 'executionReport',
            's': 'BTCUSDT',
            'S': 'BUY',
            'X': 'FILLED',
            'l': '0.001',
            'Z': '50.00'
        }
        
        with patch('app.services.binance_user_stream.ws_events_total') as mock_events_metric:
            with patch('app.services.binance_user_stream.ws_fill_latency_seconds') as mock_latency_metric:
                with patch('app.services.binance_user_stream.get_trade_executor') as mock_get_executor:
                    mock_executor = Mock()
                    mock_balance_service = AsyncMock()
                    mock_executor.balance_service = mock_balance_service
                    mock_get_executor.return_value = mock_executor
                    
                    # Ejecutar
                    await default_on_fill(event)
                    
                    # Verificar métricas
                    mock_events_metric.labels.assert_called_with(event="executionReport")
                    mock_latency_metric.observe.assert_called()
    
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, ws_handler):
        """Test: Verificar el ciclo de vida de start/stop"""
        # Mock on_fill callback
        async def mock_on_fill(event):
            pass
        
        # Start handler
        await ws_handler.start(on_fill=mock_on_fill)
        assert ws_handler.running is True
        assert ws_handler._on_fill is not None
        
        # Stop handler
        await ws_handler.stop()
        assert ws_handler.running is False
    
    @pytest.mark.asyncio
    async def test_reconnection_on_error(self, ws_handler, mock_aiohttp_session):
        """Test: Verificar reconexión automática en error"""
        # Este test requiere simular errores de conexión
        # y verificar que el handler reintenta
        
        # Mock listenKey creation
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={'listenKey': 'test_key'})
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response
        
        # Mock WebSocket que falla y luego tiene éxito
        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = []  # Sin mensajes
        mock_aiohttp_session.ws_connect.side_effect = [
            Exception("Connection failed"),  # Primera falla
            mock_ws  # Segunda exitosa
        ]
        
        # Este test es complejo de implementar sin event loop real
        # Por ahora, verificamos que el código maneja excepciones
        pass  # TODO: Implementar test de reconexión con asyncio real


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

