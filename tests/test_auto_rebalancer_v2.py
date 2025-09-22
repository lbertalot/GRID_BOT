"""
Tests para AutoRebalancer V2 - Sistema de liquidez autónoma
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.auto_rebalancer_v2 import AutoRebalancerV2


class TestAutoRebalancerV2:
    """Tests para el sistema de rebalanceo V2"""
    
    @pytest.fixture
    def rebalancer(self):
        """Fixture para crear instancia de AutoRebalancerV2"""
        with patch('app.services.auto_rebalancer_v2.get_binance_client_singleton'):
            with patch('app.services.auto_rebalancer_v2.CircuitBreakers'):
                with patch('app.services.auto_rebalancer_v2.StrategyBlacklist'):
                    return AutoRebalancerV2()
    
    def test_initialization(self, rebalancer):
        """Test de inicialización del rebalanceador"""
        assert rebalancer.min_usdt_balance == 25.0
        assert rebalancer.target_usdt_balance == 50.0
        assert rebalancer.enable_auto_rebalance == True
        assert 'SPK' in rebalancer.asset_priority
        assert 'ETHUSDT' in rebalancer.protected_assets
    
    @pytest.mark.asyncio
    async def test_check_and_rebalance_sufficient_liquidity(self, rebalancer):
        """Test cuando la liquidez es suficiente"""
        with patch.object(rebalancer, '_get_current_usdt_balance', return_value=30.0):
            with patch.object(rebalancer, '_check_circuit_breakers', return_value=True):
                result = await rebalancer.check_and_rebalance()
                
                assert result['status'] == 'sufficient'
                assert result['current_usdt'] == 30.0
    
    @pytest.mark.asyncio
    async def test_check_and_rebalance_insufficient_liquidity(self, rebalancer):
        """Test cuando la liquidez es insuficiente y necesita rebalanceo"""
        with patch.object(rebalancer, '_get_current_usdt_balance', return_value=15.0):
            with patch.object(rebalancer, '_check_circuit_breakers', return_value=True):
                with patch.object(rebalancer, '_execute_liquidity_rebalance', return_value={'status': 'success'}):
                    result = await rebalancer.check_and_rebalance()
                    
                    assert result['status'] == 'success'
                    assert 'deficit_resolved' in result
    
    @pytest.mark.asyncio
    async def test_check_circuit_breakers_blocked(self, rebalancer):
        """Test cuando los circuit breakers están activos"""
        with patch.object(rebalancer, '_check_circuit_breakers', return_value=False):
            result = await rebalancer.check_and_rebalance()
            
            assert result['status'] == 'blocked'
            assert result['reason'] == 'circuit_breakers_active'
    
    @pytest.mark.asyncio
    async def test_select_assets_for_liquidation(self, rebalancer):
        """Test de selección de activos para liquidación"""
        # Mock balances con activos disponibles
        balances = {
            'SPK': 100.0,  # Prioridad 1 - debería ser seleccionado
            'BNB': 50.0,   # Prioridad 4 - debería ser seleccionado si SPK no es suficiente
            'ETH': 10.0,   # Protegido - NO debería ser seleccionado
            'BTC': 5.0     # Prioridad 5 - debería ser seleccionado
        }
        
        with patch.object(rebalancer, '_validate_sale_parameters', return_value=True):
            with patch.object(rebalancer.binance_client, 'get_symbol_ticker') as mock_ticker:
                mock_ticker.return_value = {'price': '1.0'}  # Precio fijo para testing
                
                selected_assets = await rebalancer._select_assets_for_liquidation(balances, 50.0)
                
                # Verificar que se seleccionaron activos
                assert len(selected_assets) > 0
                
                # Verificar que SPK tiene prioridad más alta
                spk_asset = next((a for a in selected_assets if a['asset'] == 'SPK'), None)
                if spk_asset:
                    assert spk_asset['priority'] == 0  # Primera prioridad
                
                # Verificar que ETH no fue seleccionado (está protegido)
                eth_asset = next((a for a in selected_assets if a['asset'] == 'ETH'), None)
                assert eth_asset is None
    
    @pytest.mark.asyncio
    async def test_protected_assets_not_selected(self, rebalancer):
        """Test que los activos protegidos no se seleccionan para liquidación"""
        balances = {
            'ETHUSDT': 100.0,  # Protegido
            'ETH': 50.0,       # Protegido
            'SPK': 25.0        # No protegido
        }
        
        with patch.object(rebalancer, '_validate_sale_parameters', return_value=True):
            with patch.object(rebalancer.binance_client, 'get_symbol_ticker') as mock_ticker:
                mock_ticker.return_value = {'price': '1.0'}
                
                selected_assets = await rebalancer._select_assets_for_liquidation(balances, 50.0)
                
                # Verificar que solo SPK fue seleccionado
                selected_assets_names = [a['asset'] for a in selected_assets]
                assert 'ETHUSDT' not in selected_assets_names
                assert 'ETH' not in selected_assets_names
                assert 'SPK' in selected_assets_names
    
    @pytest.mark.asyncio
    async def test_blacklisted_assets_not_selected(self, rebalancer):
        """Test que los activos en blacklist no se seleccionan"""
        balances = {
            'SPK': 100.0,  # En blacklist
            'BNB': 50.0    # No en blacklist
        }
        
        # Mock blacklist para SPK
        rebalancer.strategy_blacklist.is_symbol_blacklisted = Mock(side_effect=lambda x: x == 'SPK')
        
        with patch.object(rebalancer, '_validate_sale_parameters', return_value=True):
            with patch.object(rebalancer.binance_client, 'get_symbol_ticker') as mock_ticker:
                mock_ticker.return_value = {'price': '1.0'}
                
                selected_assets = await rebalancer._select_assets_for_liquidation(balances, 50.0)
                
                # Verificar que SPK no fue seleccionado (está en blacklist)
                selected_assets_names = [a['asset'] for a in selected_assets]
                assert 'SPK' not in selected_assets_names
                assert 'BNB' in selected_assets_names
    
    @pytest.mark.asyncio
    async def test_execute_sales_success(self, rebalancer):
        """Test de ejecución exitosa de ventas"""
        assets_to_sell = [
            {
                'asset': 'SPK',
                'symbol': 'SPKUSDT',
                'quantity': 100.0,
                'price': 1.0,
                'value_usdt': 100.0
            }
        ]
        
        # Mock orden exitosa
        mock_order = {
            'orderId': '12345',
            'status': 'FILLED'
        }
        
        with patch.object(rebalancer.binance_client, 'create_order', return_value=mock_order):
            with patch.object(rebalancer, '_save_trade_to_db'):
                results = await rebalancer._execute_sales(assets_to_sell)
                
                assert len(results) == 1
                assert results[0]['status'] == 'success'
                assert results[0]['asset'] == 'SPK'
                assert results[0]['order_id'] == '12345'
    
    @pytest.mark.asyncio
    async def test_get_rebalance_status(self, rebalancer):
        """Test de obtención del estado del rebalanceo"""
        with patch.object(rebalancer, '_get_current_usdt_balance', return_value=30.0):
            with patch.object(rebalancer, '_get_all_balances', return_value={'SPK': 100.0, 'BNB': 50.0}):
                with patch.object(rebalancer.strategy_blacklist, 'is_symbol_blacklisted', return_value=False):
                    status = await rebalancer.get_rebalance_status()
                    
                    assert status['current_usdt_balance'] == 30.0
                    assert status['min_usdt_balance'] == 25.0
                    assert status['target_usdt_balance'] == 50.0
                    assert status['needs_rebalance'] == False  # 30.0 >= 25.0
                    assert 'SPK' in status['available_assets']
                    assert 'ETHUSDT' in status['protected_assets']


class TestAutoRebalancerV2Integration:
    """Tests de integración para el rebalanceador V2"""
    
    @pytest.mark.asyncio
    async def test_full_rebalance_cycle(self):
        """Test del ciclo completo de rebalanceo"""
        with patch('app.services.auto_rebalancer_v2.get_binance_client_singleton'):
            with patch('app.services.auto_rebalancer_v2.CircuitBreakers'):
                with patch('app.services.auto_rebalancer_v2.StrategyBlacklist'):
                    rebalancer = AutoRebalancerV2()
                    
                    # Mock de escenario: liquidez insuficiente
                    with patch.object(rebalancer, '_get_current_usdt_balance', return_value=15.0):
                        with patch.object(rebalancer, '_check_circuit_breakers', return_value=True):
                            with patch.object(rebalancer, '_execute_liquidity_rebalance', return_value={'status': 'success'}):
                                result = await rebalancer.check_and_rebalance()
                                
                                assert result['status'] == 'success'
                                assert 'deficit_resolved' in result
    
    @pytest.mark.asyncio
    async def test_rebalance_disabled(self):
        """Test cuando el rebalanceo está desactivado"""
        with patch('app.services.auto_rebalancer_v2.get_binance_client_singleton'):
            with patch('app.services.auto_rebalancer_v2.CircuitBreakers'):
                with patch('app.services.auto_rebalancer_v2.StrategyBlacklist'):
                    with patch.dict('os.environ', {'ENABLE_AUTO_REBALANCE': 'false'}):
                        rebalancer = AutoRebalancerV2()
                        result = await rebalancer.check_and_rebalance()
                        
                        assert result['status'] == 'disabled'
                        assert result['message'] == 'Auto-rebalance disabled'


if __name__ == "__main__":
    pytest.main([__file__])
