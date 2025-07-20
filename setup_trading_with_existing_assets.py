#!/usr/bin/env python3
"""
Script para configurar trading con activos existentes
"""

import requests
import json
import time

def setup_trading_with_existing_assets():
    """Configura trading con los activos que ya tienes"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🎯 Configurando Trading con Activos Existentes")
    print("=" * 55)
    
    # Obtener balances
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        print(f"📊 Balance actual:")
        print(f"   💰 ARS: ${balances.get('ARS', 0):,.2f}")
        print(f"   💵 USDT: ${balances.get('USDT', 0):.2f}")
        print(f"   🪙 BNB: {balances.get('BNB', 0):.6f}")
        
        # Activos disponibles para trading
        trading_assets = [
            {'symbol': 'BNB', 'min_qty': 0.001, 'reason': 'Alta liquidez, trading activo'},
            {'symbol': 'ANIME', 'min_qty': 0.01, 'reason': 'Cantidad significativa'},
            {'symbol': 'GPS', 'min_qty': 0.01, 'reason': 'Bueno para trading'},
            {'symbol': 'GUN', 'min_qty': 0.01, 'reason': 'Volatilidad interesante'},
            {'symbol': 'SIGN', 'min_qty': 0.01, 'reason': 'Oportunidades de trading'},
            {'symbol': 'SPK', 'min_qty': 0.01, 'reason': 'Potencial de crecimiento'},
            {'symbol': 'HOME', 'min_qty': 0.01, 'reason': 'Activo emergente'},
            {'symbol': 'HUMA', 'min_qty': 0.01, 'reason': 'Innovación tecnológica'}
        ]
        
        successful_configs = []
        
        for asset in trading_assets:
            symbol = asset['symbol']
            available_balance = balances.get(symbol, 0)
            
            if available_balance >= asset['min_qty']:
                print(f"\n🎯 Configurando grid para {symbol}USDT")
                print(f"   📊 Balance disponible: {available_balance:.6f}")
                
                # Calcular cantidad óptima (usar 30% del balance disponible)
                optimal_qty = available_balance * 0.3
                
                # Obtener precio actual
                try:
                    ticker_response = requests.get(f"{base_url}/api/trade/ticker/{symbol}USDT", headers={"Authorization": f"Bearer {api_key}"})
                    if ticker_response.status_code == 200:
                        current_price = float(ticker_response.json().get('price', 0))
                        
                        if current_price > 0:
                            # Calcular rango de precios (±15% del precio actual)
                            min_price = current_price * 0.85
                            max_price = current_price * 1.15
                            
                            grid_config = {
                                "symbol": f"{symbol}USDT",
                                "min_price": round(min_price, 6),
                                "max_price": round(max_price, 6),
                                "grids": 6,
                                "quantity": round(optimal_qty, 6)
                            }
                            
                            print(f"   💰 Precio actual: ${current_price:.6f}")
                            print(f"   📈 Rango: ${min_price:.6f} - ${max_price:.6f}")
                            print(f"   🎯 Cantidad: {optimal_qty:.6f}")
                            
                            # Guardar configuración
                            grid_info = {
                                'symbol': f"{symbol}USDT",
                                'quantity': optimal_qty,
                                'current_price': current_price,
                                'min_price': min_price,
                                'max_price': max_price,
                                'balance': available_balance,
                                'usdt_value': optimal_qty * current_price
                            }
                            
                            successful_configs.append(grid_info)
                            print(f"   ✅ Grid configurado para {symbol}")
                            
                        else:
                            print(f"   ❌ No se pudo obtener precio para {symbol}")
                    else:
                        print(f"   ❌ Error obteniendo precio para {symbol}")
                        
                except Exception as e:
                    print(f"   ❌ Error configurando {symbol}: {e}")
            else:
                print(f"   ⚠️ Balance insuficiente para {symbol}: {available_balance:.6f} < {asset['min_qty']}")
        
        # Guardar configuración final
        if successful_configs:
            config_data = {
                'existing_assets_grids': successful_configs,
                'setup_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_assets': len(successful_configs),
                'total_usdt_value': sum(g['usdt_value'] for g in successful_configs)
            }
            
            with open('existing_assets_grids_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)
            
            print(f"\n🎉 Configuración completada!")
            print(f"📊 Grids configurados: {len(successful_configs)}")
            print(f"💰 Valor total: ${config_data['total_usdt_value']:.2f} USDT")
            print(f"💾 Configuración guardada en 'existing_assets_grids_config.json'")
            
            # Enviar alerta de Telegram
            alert_message = f"🎯 Trading con Activos Existentes Configurado\n\n"
            alert_message += f"📊 Grids activos: {len(successful_configs)}\n"
            alert_message += f"💰 Valor total: ${config_data['total_usdt_value']:.2f} USDT\n"
            alert_message += f"🕒 Timestamp: {config_data['setup_timestamp']}\n\n"
            
            for grid in successful_configs:
                alert_message += f"• {grid['symbol']}: {grid['quantity']:.6f}\n"
                alert_message += f"  💰 Precio: ${grid['current_price']:.6f}\n"
                alert_message += f"  📈 Rango: ${grid['min_price']:.6f} - ${grid['max_price']:.6f}\n\n"
            
            alert_message += f"🚀 ¡Ahora puedes recibir alertas de múltiples activos!"
            alert_message += f"\n📱 GridBot operará con los activos disponibles"
            
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
    success = setup_trading_with_existing_assets()
    
    if success:
        print(f"\n🎉 ¡Trading con activos existentes configurado!")
        print(f"📱 Recibirás alertas de múltiples activos")
        print(f"🤖 GridBot está listo para operar con diversificación")
    else:
        print(f"\n❌ No se pudo completar la configuración")

if __name__ == "__main__":
    main() 