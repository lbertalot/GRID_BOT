import pytest
import os
from binance import Client
from unittest.mock import patch, MagicMock
from app.services.telegram_alert import send_telegram_alert

class TestOrderSimulation:
    """Tests de simulación de órdenes sin ejecutarlas realmente"""
    
    @pytest.fixture
    def binance_client(self):
        """Fixture para crear cliente de Binance"""
        return Client()
    
    def test_simulate_market_buy_order(self, binance_client):
        """Test de simulación de orden de compra de mercado"""
        symbol = 'BTCUSDT'
        
        try:
            # Obtener información real del símbolo
            symbol_info = binance_client.get_symbol_info(symbol)
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            
            # Calcular cantidad mínima
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
            
            min_qty = float(lot_size_filter['minQty']) if lot_size_filter else 0.001
            min_notional = float(min_notional_filter['minNotional']) if min_notional_filter else 10.0
            current_price = float(ticker['price'])
            
            # Calcular cantidad mínima
            min_quantity_for_notional = min_notional / current_price
            actual_min_quantity = max(min_qty, min_quantity_for_notional)
            
            print(f"🧪 Simulando orden de compra de mercado:")
            print(f"   Símbolo: {symbol}")
            print(f"   Cantidad: {actual_min_quantity}")
            print(f"   Precio actual: ${current_price:,.2f}")
            print(f"   Costo estimado: ${actual_min_quantity * current_price:.2f}")
            print(f"   Tipo: MARKET")
            
            # Simular resultado de orden
            simulated_result = {
                "symbol": symbol,
                "orderId": 12345,
                "status": "FILLED",
                "side": "BUY",
                "type": "MARKET",
                "quantity": str(actual_min_quantity),
                "fills": [
                    {
                        "price": str(current_price),
                        "qty": str(actual_min_quantity),
                        "commission": "0.000001",
                        "commissionAsset": "BTC"
                    }
                ]
            }
            
            print(f"   ✅ Simulación completada")
            print(f"   Order ID: {simulated_result['orderId']}")
            print(f"   Status: {simulated_result['status']}")
            print(f"   Precio de ejecución: ${simulated_result['fills'][0]['price']}")
            print(f"   Cantidad ejecutada: {simulated_result['fills'][0]['qty']}")
            print(f"   Comisión: {simulated_result['fills'][0]['commission']} {simulated_result['fills'][0]['commissionAsset']}")
            
            # Enviar alerta de Telegram
            try:
                send_telegram_alert(f"🧪 Simulación: Orden de compra - {symbol} {actual_min_quantity} @ ${current_price:,.2f}")
            except Exception as e:
                print(f"   ⚠️ Error enviando alerta Telegram: {e}")
            
            assert simulated_result['status'] == 'FILLED', "La orden simulada debería estar completada"
            assert simulated_result['symbol'] == symbol, "El símbolo debería coincidir"
            assert float(simulated_result['fills'][0]['price']) > 0, "El precio debería ser mayor que 0"
            
            return simulated_result
            
        except Exception as e:
            pytest.fail(f"Error simulando orden de compra: {e}")
    
    def test_simulate_market_sell_order(self, binance_client):
        """Test de simulación de orden de venta de mercado"""
        symbol = 'BTCUSDT'
        
        try:
            # Obtener información real del símbolo
            symbol_info = binance_client.get_symbol_info(symbol)
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            
            # Calcular cantidad mínima
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
            
            min_qty = float(lot_size_filter['minQty']) if lot_size_filter else 0.001
            min_notional = float(min_notional_filter['minNotional']) if min_notional_filter else 10.0
            current_price = float(ticker['price'])
            
            # Calcular cantidad mínima
            min_quantity_for_notional = min_notional / current_price
            actual_min_quantity = max(min_qty, min_quantity_for_notional)
            
            print(f"🧪 Simulando orden de venta de mercado:")
            print(f"   Símbolo: {symbol}")
            print(f"   Cantidad: {actual_min_quantity}")
            print(f"   Precio actual: ${current_price:,.2f}")
            print(f"   Valor estimado: ${actual_min_quantity * current_price:.2f}")
            print(f"   Tipo: MARKET")
            
            # Simular resultado de orden
            simulated_result = {
                "symbol": symbol,
                "orderId": 12346,
                "status": "FILLED",
                "side": "SELL",
                "type": "MARKET",
                "quantity": str(actual_min_quantity),
                "fills": [
                    {
                        "price": str(current_price),
                        "qty": str(actual_min_quantity),
                        "commission": "0.01",
                        "commissionAsset": "USDT"
                    }
                ]
            }
            
            print(f"   ✅ Simulación completada")
            print(f"   Order ID: {simulated_result['orderId']}")
            print(f"   Status: {simulated_result['status']}")
            print(f"   Precio de ejecución: ${simulated_result['fills'][0]['price']}")
            print(f"   Cantidad ejecutada: {simulated_result['fills'][0]['qty']}")
            print(f"   Comisión: {simulated_result['fills'][0]['commission']} {simulated_result['fills'][0]['commissionAsset']}")
            
            # Enviar alerta de Telegram
            try:
                send_telegram_alert(f"🧪 Simulación: Orden de venta - {symbol} {actual_min_quantity} @ ${current_price:,.2f}")
            except Exception as e:
                print(f"   ⚠️ Error enviando alerta Telegram: {e}")
            
            assert simulated_result['status'] == 'FILLED', "La orden simulada debería estar completada"
            assert simulated_result['symbol'] == symbol, "El símbolo debería coincidir"
            assert float(simulated_result['fills'][0]['price']) > 0, "El precio debería ser mayor que 0"
            
            return simulated_result
            
        except Exception as e:
            pytest.fail(f"Error simulando orden de venta: {e}")
    
    def test_simulate_limit_order(self, binance_client):
        """Test de simulación de orden límite"""
        symbol = 'BTCUSDT'
        
        try:
            # Obtener información real del símbolo
            symbol_info = binance_client.get_symbol_info(symbol)
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            
            # Calcular cantidad mínima
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
            
            min_qty = float(lot_size_filter['minQty']) if lot_size_filter else 0.001
            min_notional = float(min_notional_filter['minNotional']) if min_notional_filter else 10.0
            current_price = float(ticker['price'])
            
            # Calcular cantidad mínima
            min_quantity_for_notional = min_notional / current_price
            actual_min_quantity = max(min_qty, min_quantity_for_notional)
            
            # Calcular precio límite (5% por debajo del precio actual)
            limit_price = current_price * 0.95
            
            print(f"🧪 Simulando orden límite:")
            print(f"   Símbolo: {symbol}")
            print(f"   Cantidad: {actual_min_quantity}")
            print(f"   Precio límite: ${limit_price:,.2f}")
            print(f"   Precio actual: ${current_price:,.2f}")
            print(f"   Tipo: LIMIT")
            
            # Simular resultado de orden
            simulated_result = {
                "symbol": symbol,
                "orderId": 12347,
                "status": "NEW",
                "side": "BUY",
                "type": "LIMIT",
                "quantity": str(actual_min_quantity),
                "price": str(limit_price),
                "timeInForce": "GTC"
            }
            
            print(f"   ✅ Simulación completada")
            print(f"   Order ID: {simulated_result['orderId']}")
            print(f"   Status: {simulated_result['status']}")
            print(f"   Precio límite: ${simulated_result['price']}")
            
            # Simular cancelación
            cancel_result = {
                "symbol": symbol,
                "orderId": 12347,
                "status": "CANCELED"
            }
            
            print(f"   ✅ Orden cancelada simulada")
            
            # Enviar alerta de Telegram
            try:
                send_telegram_alert(f"🧪 Simulación: Orden límite creada y cancelada - {symbol} {actual_min_quantity} @ ${limit_price:,.2f}")
            except Exception as e:
                print(f"   ⚠️ Error enviando alerta Telegram: {e}")
            
            assert simulated_result['status'] == 'NEW', "La orden simulada debería estar en estado NEW"
            assert simulated_result['symbol'] == symbol, "El símbolo debería coincidir"
            assert float(simulated_result['price']) > 0, "El precio debería ser mayor que 0"
            
            return simulated_result
            
        except Exception as e:
            pytest.fail(f"Error simulando orden límite: {e}")
    
    def test_simulate_grid_trading(self, binance_client):
        """Test de simulación de trading grid"""
        symbol = 'BTCUSDT'
        
        try:
            # Obtener precio actual
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Configurar parámetros de grid
            min_price = current_price * 0.98  # 2% abajo del precio actual
            max_price = current_price * 1.02  # 2% arriba del precio actual
            grids = 3
            
            print(f"🧪 Simulando trading Grid:")
            print(f"   Símbolo: {symbol}")
            print(f"   Precio actual: ${current_price:,.2f}")
            print(f"   Rango: ${min_price:,.2f} - ${max_price:,.2f}")
            print(f"   Grids: {grids}")
            
            # Simular niveles de grid
            grid_levels = []
            for i in range(grids):
                level = min_price + (max_price - min_price) * i / (grids - 1)
                grid_levels.append(level)
            
            print(f"   Niveles calculados: {[f'${level:.2f}' for level in grid_levels]}")
            
            # Simular órdenes en cada nivel
            grid_orders = []
            for i, level in enumerate(grid_levels):
                order = {
                    "level": i + 1,
                    "price": level,
                    "action": "BUY" if level < current_price else "SELL",
                    "quantity": 0.001,
                    "status": "PENDING"
                }
                grid_orders.append(order)
            
            print(f"   Órdenes simuladas:")
            for order in grid_orders:
                print(f"     Nivel {order['level']}: {order['action']} {order['quantity']} @ ${order['price']:.2f}")
            
            # Enviar alerta de Telegram
            try:
                send_telegram_alert(f"🧪 Simulación: Grid trading configurado - {symbol} {grids} niveles")
            except Exception as e:
                print(f"   ⚠️ Error enviando alerta Telegram: {e}")
            
            assert len(grid_levels) == grids, "Debería tener el número correcto de niveles"
            assert len(grid_orders) == grids, "Debería tener el número correcto de órdenes"
            
            print(f"   ✅ Simulación de Grid trading completada")
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'grid_levels': grid_levels,
                'grid_orders': grid_orders
            }
            
        except Exception as e:
            pytest.fail(f"Error simulando Grid trading: {e}")
    
    def test_simulate_profit_calculation(self, binance_client):
        """Test de simulación de cálculo de ganancias"""
        symbol = 'BTCUSDT'
        
        try:
            # Obtener precio actual
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Simular operaciones
            buy_price = current_price * 0.95  # Compra 5% más barato
            sell_price = current_price * 1.05  # Venta 5% más cara
            quantity = 0.001
            
            # Calcular ganancias
            buy_cost = buy_price * quantity
            sell_revenue = sell_price * quantity
            gross_profit = sell_revenue - buy_cost
            profit_percentage = (gross_profit / buy_cost) * 100
            
            # Simular comisiones (0.1% por operación)
            buy_commission = buy_cost * 0.001
            sell_commission = sell_revenue * 0.001
            total_commission = buy_commission + sell_commission
            
            # Ganancia neta
            net_profit = gross_profit - total_commission
            net_profit_percentage = (net_profit / buy_cost) * 100
            
            print(f"🧪 Simulación de cálculo de ganancias:")
            print(f"   Símbolo: {symbol}")
            print(f"   Precio actual: ${current_price:,.2f}")
            print(f"   Precio de compra: ${buy_price:,.2f}")
            print(f"   Precio de venta: ${sell_price:,.2f}")
            print(f"   Cantidad: {quantity}")
            print(f"   Costo de compra: ${buy_cost:.4f}")
            print(f"   Ingreso de venta: ${sell_revenue:.4f}")
            print(f"   Ganancia bruta: ${gross_profit:.4f} ({profit_percentage:.2f}%)")
            print(f"   Comisiones totales: ${total_commission:.4f}")
            print(f"   Ganancia neta: ${net_profit:.4f} ({net_profit_percentage:.2f}%)")
            
            # Enviar alerta de Telegram
            try:
                send_telegram_alert(f"🧪 Simulación: Ganancia calculada - {symbol} {net_profit_percentage:.2f}% neto")
            except Exception as e:
                print(f"   ⚠️ Error enviando alerta Telegram: {e}")
            
            assert net_profit > 0, "La ganancia neta debería ser positiva"
            assert net_profit_percentage > 0, "El porcentaje de ganancia debería ser positivo"
            
            print(f"   ✅ Simulación de cálculo de ganancias completada")
            
            return {
                'symbol': symbol,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'quantity': quantity,
                'net_profit': net_profit,
                'net_profit_percentage': net_profit_percentage
            }
            
        except Exception as e:
            pytest.fail(f"Error simulando cálculo de ganancias: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 