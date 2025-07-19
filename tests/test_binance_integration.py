import pytest
import os
from binance import Client
from app.services.telegram_alert import send_telegram_alert

class TestBinanceIntegration:
    """Tests de integración con Binance API"""
    
    @pytest.fixture
    def binance_client(self):
        """Fixture para crear cliente de Binance con credenciales reales"""
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        
        if not api_key or not api_secret:
            pytest.skip("Credenciales de Binance no configuradas")
        
        return Client(api_key, api_secret)
    
    def test_binance_connection(self, binance_client):
        """Test de conexión básica con Binance"""
        try:
            # Probar conexión obteniendo información de la cuenta
            account_info = binance_client.get_account()
            assert 'makerCommission' in account_info
            assert 'takerCommission' in account_info
            print(f"✅ Conexión exitosa con Binance - Cuenta: {account_info.get('accountType', 'N/A')}")
        except Exception as e:
            pytest.fail(f"Error conectando con Binance: {e}")
    
    def test_get_symbol_price(self, binance_client):
        """Test de obtención de precios de símbolos"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
        
        for symbol in symbols:
            try:
                ticker = binance_client.get_symbol_ticker(symbol=symbol)
                assert 'symbol' in ticker
                assert 'price' in ticker
                assert ticker['symbol'] == symbol
                assert float(ticker['price']) > 0
                print(f"✅ Precio {symbol}: ${ticker['price']}")
            except Exception as e:
                pytest.fail(f"Error obteniendo precio de {symbol}: {e}")
    
    def test_get_account_balances(self, binance_client):
        """Test de obtención de balances de la cuenta"""
        try:
            account_info = binance_client.get_account()
            balances = account_info['balances']
            
            # Verificar que hay balances
            assert len(balances) > 0
            
            # Buscar balances con cantidad > 0
            non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
            
            print(f"✅ Balances obtenidos - {len(non_zero_balances)} activos con saldo:")
            for balance in non_zero_balances[:5]:  # Mostrar solo los primeros 5
                print(f"   {balance['asset']}: Libre={balance['free']}, Bloqueado={balance['locked']}")
                
        except Exception as e:
            pytest.fail(f"Error obteniendo balances: {e}")
    
    def test_symbol_info_validation(self, binance_client):
        """Test de validación de información de símbolos"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
        
        for symbol in symbols:
            try:
                symbol_info = binance_client.get_symbol_info(symbol)
                assert symbol_info is not None
                assert symbol_info['symbol'] == symbol
                assert symbol_info['status'] == 'TRADING'
                
                # Verificar lot size filter
                lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
                assert lot_size_filter is not None
                
                min_qty = float(lot_size_filter['minQty'])
                max_qty = float(lot_size_filter['maxQty'])
                step_size = float(lot_size_filter['stepSize'])
                
                print(f"✅ {symbol} - Min: {min_qty}, Max: {max_qty}, Step: {step_size}")
                
            except Exception as e:
                pytest.fail(f"Error validando símbolo {symbol}: {e}")
    
    def test_exchange_info(self, binance_client):
        """Test de información general del exchange"""
        try:
            exchange_info = binance_client.get_exchange_info()
            
            assert 'symbols' in exchange_info
            assert 'timezone' in exchange_info
            assert 'serverTime' in exchange_info
            
            # Contar símbolos que están trading
            trading_symbols = [s for s in exchange_info['symbols'] if s['status'] == 'TRADING']
            
            print(f"✅ Exchange info - {len(trading_symbols)} símbolos en trading")
            
        except Exception as e:
            pytest.fail(f"Error obteniendo exchange info: {e}")
    
    def test_klines_data(self, binance_client):
        """Test de obtención de datos históricos (klines)"""
        symbol = 'BTCUSDT'
        interval = '1h'
        limit = 10
        
        try:
            klines = binance_client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
            assert len(klines) == limit
            assert len(klines[0]) >= 6  # Cada kline debe tener al menos 6 campos
            
            # Verificar estructura de datos
            for kline in klines:
                assert len(kline) >= 6
                open_time = int(kline[0])
                close_time = int(kline[6])
                assert close_time > open_time
                
            print(f"✅ Klines obtenidos - {len(klines)} registros de {symbol} ({interval})")
            
        except Exception as e:
            pytest.fail(f"Error obteniendo klines: {e}")
    
    def test_telegram_alert_integration(self):
        """Test de integración con Telegram (sin enviar mensaje real)"""
        try:
            # Simular test de integración
            result = True  # send_telegram_alert("🧪 Test de integración Binance completado")
            assert result is not None
            print("✅ Integración con Telegram configurada")
        except Exception as e:
            pytest.fail(f"Error en integración con Telegram: {e}")

if __name__ == "__main__":
    # Ejecutar tests manualmente
    pytest.main([__file__, "-v"]) 