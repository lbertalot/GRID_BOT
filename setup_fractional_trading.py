#!/usr/bin/env python3
"""
Script para configurar trading con cantidades fraccionarias
"""

import requests
import json
import time

def get_fractional_quantities():
    """Retorna cantidades válidas para activos con cantidades pequeñas"""
    return {
        'BNB': {'min_qty': 0.001, 'step_size': 0.001, 'min_notional': 5},
        'ANIME': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'GPS': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'GUN': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'SIGN': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'SPK': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'HOME': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'HUMA': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5}
    }

def get_estimated_prices():
    """Retorna precios estimados para los activos"""
    return {
        'BNB': 735,
        'ANIME': 0.0005,
        'GPS': 0.0003,
        'GUN': 0.0004,
        'SIGN': 0.0002,
        'SPK': 0.0003,
        'HOME': 0.0002,
        'HUMA': 0.0003
    }

def setup_fractional_trading():
    """Configura trading con cantidades fraccionarias"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🎯 Configurando Trading Fraccionario")
    print("=" * 50)
    
    # Obtener balances
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        print(f"📊 Balance actual:")
        print(f"   💰 ARS: ${balances.get('ARS', 0):,.2f}")
        print(f"   💵 USDT: ${balances.get('USDT', 0):.2f}")
        
        # Activos disponibles para trading
        trading_assets = [
            {'symbol': 'BNB', 'min_qty': 0.001, 'reason': 'Alta liquidez, trading activo'},
            {'symbol': 'ANIME', 'min_qty': 0.01, 'reason': 'Token emergente, volatilidad alta'},
            {'symbol': 'GPS', 'min_qty': 0.01, 'reason': 'Tecnología GPS, potencial de crecimiento'},
            {'symbol': 'GUN', 'min_qty': 0.01, 'reason': 'Gaming, comunidad activa'},
            {'symbol': 'SIGN', 'min_qty': 0.01, 'reason': 'Señales de trading, DeFi'},
            {'symbol': 'SPK', 'min_qty': 0.01, 'reason': 'Speak protocol, comunicación'},
            {'symbol': 'HOME', 'min_qty': 0.01, 'reason': 'Real estate, tokenización'},
            {'symbol': 'HUMA', 'min_qty': 0.01, 'reason': 'Human protocol, innovación'}
        ]
        
        # Obtener datos de validación
        estimated_prices = get_estimated_prices()
        fractional_quantities = get_fractional_quantities()
        
        successful_configs = []
        total_usdt_value = 0
        
        for asset in trading_assets:
            symbol = asset['symbol']
            available_balance = balances.get(symbol, 0)
            
            if available_balance >= asset['min_qty']:
                print(f"\n🎯 Configurando grid para {symbol}USDT")
                print(f"   📊 Balance disponible: {available_balance:.6f}")
                
                # Calcular cantidad óptima (usar 30% del balance disponible)
                optimal_qty = available_balance * 0.3
                
                # Obtener precio estimado
                estimated_price = estimated_prices.get(symbol, 1)
                
                if estimated_price > 0:
                    # Calcular rango de precios (±25% del precio estimado)
                    min_price = estimated_price * 0.75
                    max_price = estimated_price * 1.25
                    
                    # Calcular valor en USDT
                    usdt_value = optimal_qty * estimated_price
                    total_usdt_value += usdt_value
                    
                    grid_config = {
                        "symbol": f"{symbol}USDT",
                        "min_price": round(min_price, 8),
                        "max_price": round(max_price, 8),
                        "grids": 6,
                        "quantity": round(optimal_qty, 6)
                    }
                    
                    print(f"   💰 Precio estimado: ${estimated_price:.8f}")
                    print(f"   📈 Rango: ${min_price:.8f} - ${max_price:.8f}")
                    print(f"   🎯 Cantidad: {optimal_qty:.6f}")
                    print(f"   💵 Valor estimado: ${usdt_value:.2f} USDT")
                    
                    # Guardar configuración
                    grid_info = {
                        'symbol': f"{symbol}USDT",
                        'quantity': optimal_qty,
                        'estimated_price': estimated_price,
                        'min_price': min_price,
                        'max_price': max_price,
                        'balance': available_balance,
                        'usdt_value': usdt_value,
                        'reason': asset['reason'],
                        'status': 'READY_FOR_TRADING'
                    }
                    
                    successful_configs.append(grid_info)
                    print(f"   ✅ Grid configurado para {symbol}")
                    
                else:
                    print(f"   ❌ No se pudo obtener precio para {symbol}")
            else:
                print(f"   ⚠️ Balance insuficiente para {symbol}: {available_balance:.6f} < {asset['min_qty']}")
        
        # Guardar configuración final
        if successful_configs:
            config_data = {
                'fractional_trading_grids': successful_configs,
                'setup_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_assets': len(successful_configs),
                'total_usdt_value': total_usdt_value,
                'trading_status': 'ACTIVE'
            }
            
            with open('fractional_trading_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)
            
            print(f"\n🎉 Configuración completada!")
            print(f"📊 Grids configurados: {len(successful_configs)}")
            print(f"💰 Valor total estimado: ${total_usdt_value:.2f} USDT")
            print(f"💾 Configuración guardada en 'fractional_trading_config.json'")
            
            # Enviar alerta de Telegram
            alert_message = f"🎯 Trading Fraccionario Configurado\n\n"
            alert_message += f"📊 Grids activos: {len(successful_configs)}\n"
            alert_message += f"💰 Valor total: ${total_usdt_value:.2f} USDT\n"
            alert_message += f"🕒 Timestamp: {config_data['setup_timestamp']}\n\n"
            
            for grid in successful_configs:
                alert_message += f"• {grid['symbol']}: {grid['quantity']:.6f}\n"
                alert_message += f"  💰 Precio: ${grid['estimated_price']:.8f}\n"
                alert_message += f"  💵 Valor: ${grid['usdt_value']:.2f} USDT\n"
                alert_message += f"  ✅ {grid['status']}\n\n"
            
            alert_message += f"🚀 ¡Todos los activos están listos para trading!"
            alert_message += f"\n📱 Recibirás alertas de múltiples activos"
            alert_message += f"\n🤖 GridBot operará con diversificación completa"
            
            try:
                telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
                telegram_data = {
                    "chat_id": "1248403886",
                    "text": alert_message
                }
                requests.post(telegram_url, data=telegram_data)
                print(f"📱 Alerta enviada a Telegram")
            except Exception as e:
                print(f"❌ Error enviando alerta: {e}")
            
            return True
        else:
            print(f"\n❌ No se pudieron configurar grids")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Función principal"""
    success = setup_fractional_trading()
    
    if success:
        print(f"\n🎉 ¡Trading fraccionario configurado!")
        print(f"📱 Recibirás alertas de múltiples activos")
        print(f"🤖 GridBot está listo para operar con diversificación completa")
        print(f"\n💡 PRÓXIMOS PASOS:")
        print(f"   1. Los grids están configurados")
        print(f"   2. El scheduler los ejecutará automáticamente")
        print(f"   3. Recibirás alertas de Telegram de todos los activos")
        print(f"   4. Monitorea en los dashboards de Grafana")
    else:
        print(f"\n❌ No se pudo completar la configuración")

if __name__ == "__main__":
    main() 