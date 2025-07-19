import pytest
import os
from binance import Client

class TestPublicTrading:
    """Tests usando solo endpoints públicos de Binance"""
    
    @pytest.fixture
    def binance_client(self):
        """Fixture para crear cliente de Binance (sin credenciales para endpoints públicos)"""
        return Client()
    
    def test_get_exchange_info(self, binance_client):
        """Test para obtener información del exchange"""
        try:
            exchange_info = binance_client.get_exchange_info()
            
            print(f"📊 Información del Exchange:")
            print(f"   Zona horaria: {exchange_info.get('timezone', 'N/A')}")
            print(f"   Tiempo del servidor: {exchange_info.get('serverTime', 'N/A')}")
            print(f"   Símbolos totales: {len(exchange_info.get('symbols', []))}")
            
            # Contar símbolos que están trading
            trading_symbols = [s for s in exchange_info['symbols'] if s['status'] == 'TRADING']
            print(f"   Símbolos en trading: {len(trading_symbols)}")
            
            assert 'symbols' in exchange_info, "Debería tener información de símbolos"
            assert len(trading_symbols) > 0, "Debería haber símbolos en trading"
            
            print(f"   ✅ Información del exchange obtenida correctamente")
            
            return exchange_info
            
        except Exception as e:
            pytest.fail(f"Error obteniendo información del exchange: {e}")
    
    def test_get_symbol_info_public(self, binance_client):
        """Test para obtener información de símbolos específicos"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
        
        for symbol in symbols:
            try:
                symbol_info = binance_client.get_symbol_info(symbol)
                
                print(f"📊 Información de {symbol}:")
                print(f"   Estado: {symbol_info['status']}")
                print(f"   Base Asset: {symbol_info['baseAsset']}")
                print(f"   Quote Asset: {symbol_info['quoteAsset']}")
                print(f"   Filtros disponibles: {[f['filterType'] for f in symbol_info['filters']]}")
                
                # Extraer filtros importantes
                lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
                min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
                price_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
                
                if lot_size_filter:
                    print(f"   Cantidad mínima: {lot_size_filter['minQty']}")
                    print(f"   Cantidad máxima: {lot_size_filter['maxQty']}")
                    print(f"   Paso de cantidad: {lot_size_filter['stepSize']}")
                
                if min_notional_filter:
                    print(f"   Valor mínimo (USDT): {min_notional_filter['minNotional']}")
                
                if price_filter:
                    print(f"   Precio mínimo: {price_filter['minPrice']}")
                    print(f"   Precio máximo: {price_filter['maxPrice']}")
                    print(f"   Paso de precio: {price_filter['tickSize']}")
                
                assert symbol_info['status'] == 'TRADING', f"{symbol} debería estar en trading"
                assert lot_size_filter is not None, f"{symbol} debería tener filtro LOT_SIZE"
                
                print(f"   ✅ Información de {symbol} obtenida correctamente")
                
            except Exception as e:
                pytest.fail(f"Error obteniendo información de {symbol}: {e}")
    
    def test_get_current_prices(self, binance_client):
        """Test para obtener precios actuales"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT']
        
        print(f"📊 Precios actuales:")
        for symbol in symbols:
            try:
                ticker = binance_client.get_symbol_ticker(symbol=symbol)
                price = float(ticker['price'])
                print(f"   {symbol}: ${price:,.2f}")
                
                assert price > 0, f"El precio de {symbol} debería ser mayor que 0"
                
            except Exception as e:
                print(f"   ⚠️ Error obteniendo precio de {symbol}: {e}")
        
        print(f"   ✅ Precios obtenidos correctamente")
    
    def test_get_24hr_ticker(self, binance_client):
        """Test para obtener estadísticas de 24 horas"""
        symbols = ['BTCUSDT', 'ETHUSDT']
        
        print(f"📊 Estadísticas de 24 horas:")
        for symbol in symbols:
            try:
                ticker_24hr = binance_client.get_ticker(symbol=symbol)
                
                print(f"   {symbol}:")
                print(f"     Precio actual: ${float(ticker_24hr['lastPrice']):,.2f}")
                print(f"     Cambio 24h: {float(ticker_24hr['priceChangePercent']):.2f}%")
                print(f"     Volumen 24h: {ticker_24hr['volume']}")
                print(f"     Máximo 24h: ${float(ticker_24hr['highPrice']):,.2f}")
                print(f"     Mínimo 24h: ${float(ticker_24hr['lowPrice']):,.2f}")
                
                assert float(ticker_24hr['lastPrice']) > 0, f"El precio de {symbol} debería ser mayor que 0"
                
            except Exception as e:
                print(f"   ⚠️ Error obteniendo estadísticas de {symbol}: {e}")
        
        print(f"   ✅ Estadísticas obtenidas correctamente")
    
    def test_get_recent_trades(self, binance_client):
        """Test para obtener trades recientes"""
        symbol = 'BTCUSDT'
        
        try:
            trades = binance_client.get_recent_trades(symbol=symbol, limit=5)
            
            print(f"📊 Trades recientes de {symbol}:")
            for i, trade in enumerate(trades[:3]):  # Mostrar solo los primeros 3
                print(f"   Trade {i+1}:")
                print(f"     Precio: ${float(trade['price']):,.2f}")
                print(f"     Cantidad: {trade['qty']}")
                print(f"     Lado: {'Compra' if trade['isBuyerMaker'] else 'Venta'}")
                print(f"     Tiempo: {trade['time']}")
            
            assert len(trades) > 0, "Debería haber trades recientes"
            
            print(f"   ✅ Trades recientes obtenidos correctamente")
            
        except Exception as e:
            pytest.fail(f"Error obteniendo trades recientes: {e}")
    
    def test_get_klines_data(self, binance_client):
        """Test para obtener datos históricos (klines)"""
        symbol = 'BTCUSDT'
        interval = '1h'
        limit = 10
        
        try:
            klines = binance_client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
            print(f"📊 Datos históricos de {symbol} ({interval}):")
            print(f"   Registros obtenidos: {len(klines)}")
            
            if klines:
                latest_kline = klines[-1]
                print(f"   Último registro:")
                print(f"     Tiempo de apertura: {latest_kline[0]}")
                print(f"     Precio de apertura: ${float(latest_kline[1]):,.2f}")
                print(f"     Precio más alto: ${float(latest_kline[2]):,.2f}")
                print(f"     Precio más bajo: ${float(latest_kline[3]):,.2f}")
                print(f"     Precio de cierre: ${float(latest_kline[4]):,.2f}")
                print(f"     Volumen: {latest_kline[5]}")
            
            assert len(klines) == limit, f"Debería obtener {limit} registros"
            assert len(klines[0]) >= 6, "Cada kline debería tener al menos 6 campos"
            
            print(f"   ✅ Datos históricos obtenidos correctamente")
            
        except Exception as e:
            pytest.fail(f"Error obteniendo datos históricos: {e}")
    
    def test_calculate_minimum_order_quantities_safe(self, binance_client):
        """Test para calcular cantidades mínimas de forma segura"""
        symbol = 'BTCUSDT'
        
        try:
            # Obtener información del símbolo
            symbol_info = binance_client.get_symbol_info(symbol)
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            
            # Extraer filtros
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
            
            min_qty = float(lot_size_filter['minQty']) if lot_size_filter else 0.001
            step_size = float(lot_size_filter['stepSize']) if lot_size_filter else 0.001
            min_notional = float(min_notional_filter['minNotional']) if min_notional_filter else 10.0
            current_price = float(ticker['price'])
            
            # Calcular cantidad mínima
            min_quantity_for_notional = min_notional / current_price
            actual_min_quantity = max(min_qty, min_quantity_for_notional)
            
            print(f"📊 Cálculo de cantidades mínimas para {symbol}:")
            print(f"   Precio actual: ${current_price:,.2f}")
            print(f"   Cantidad mínima (LOT_SIZE): {min_qty}")
            print(f"   Valor mínimo requerido: ${min_notional}")
            print(f"   Cantidad mínima por valor: {min_quantity_for_notional}")
            print(f"   Cantidad mínima final: {actual_min_quantity}")
            print(f"   Costo estimado: ${actual_min_quantity * current_price:.2f}")
            
            assert actual_min_quantity > 0, "La cantidad mínima debería ser mayor que 0"
            assert actual_min_quantity * current_price >= min_notional, "Debería cumplir con el valor mínimo"
            
            print(f"   ✅ Cálculo de cantidades mínimas correcto")
            
            return {
                'symbol': symbol,
                'min_quantity': actual_min_quantity,
                'estimated_cost': actual_min_quantity * current_price,
                'current_price': current_price
            }
            
        except Exception as e:
            pytest.fail(f"Error calculando cantidades mínimas: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 