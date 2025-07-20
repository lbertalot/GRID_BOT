#!/usr/bin/env python3
"""
Script para configurar grids con múltiples activos
"""

import requests
import json
import time

def setup_multi_asset_grids():
    """Configura grids con múltiples activos disponibles"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🎯 Configurando Grids Multi-Asset")
    print("=" * 50)
    
    # Obtener balances
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        # Activos recomendados para trading
        recommended_assets = [
            {'symbol': 'ANIME', 'min_qty': 0.01, 'max_qty': 0.05},
            {'symbol': 'GPS', 'min_qty': 0.01, 'max_qty': 0.03},
            {'symbol': 'GUN', 'min_qty': 0.01, 'max_qty': 0.03},
            {'symbol': 'SIGN', 'min_qty': 0.01, 'max_qty': 0.02},
            {'symbol': 'SPK', 'min_qty': 0.01, 'max_qty': 0.02},
            {'symbol': 'HOME', 'min_qty': 0.01, 'max_qty': 0.02}
        ]
        
        successful_grids = []
        
        for asset in recommended_assets:
            symbol = asset['symbol']
            available_balance = balances.get(symbol, 0)
            
            if available_balance >= asset['min_qty']:
                print(f"\n🎯 Configurando grid para {symbol}USDT")
                print(f"   📊 Balance disponible: {available_balance:.6f}")
                
                # Calcular cantidad óptima (usar 50% del balance disponible)
                optimal_qty = min(available_balance * 0.5, asset['max_qty'])
                
                # Obtener precio actual
                try:
                    ticker_response = requests.get(f"{base_url}/api/trade/ticker/{symbol}USDT", headers={"Authorization": f"Bearer {api_key}"})
                    if ticker_response.status_code == 200:
                        current_price = float(ticker_response.json().get('price', 0))
                        
                        if current_price > 0:
                            # Calcular rango de precios (±10% del precio actual)
                            min_price = current_price * 0.9
                            max_price = current_price * 1.1
                            
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
                                'balance': available_balance
                            }
                            
                            successful_grids.append(grid_info)
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
        if successful_grids:
            config_data = {
                'multi_asset_grids': successful_grids,
                'setup_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_assets': len(successful_grids)
            }
            
            with open('multi_asset_grids_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)
            
            print(f"\n🎉 Configuración completada!")
            print(f"📊 Grids configurados: {len(successful_grids)}")
            print(f"💾 Configuración guardada en 'multi_asset_grids_config.json'")
            
            # Enviar alerta de Telegram
            alert_message = f"🎯 Grids Multi-Asset Configurados\n\n"
            alert_message += f"📊 Assets configurados: {len(successful_grids)}\n"
            alert_message += f"🕒 Timestamp: {config_data['setup_timestamp']}\n\n"
            
            for grid in successful_grids:
                alert_message += f"• {grid['symbol']}: {grid['quantity']:.6f}\n"
                alert_message += f"  💰 Precio: ${grid['current_price']:.6f}\n"
                alert_message += f"  📈 Rango: ${grid['min_price']:.6f} - ${grid['max_price']:.6f}\n\n"
            
            alert_message += f"🚀 ¡Ahora puedes recibir alertas de múltiples activos!"
            
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
    success = setup_multi_asset_grids()
    
    if success:
        print(f"\n🎉 ¡Grids multi-asset configurados exitosamente!")
        print(f"📱 Recibirás alertas de múltiples activos")
        print(f"🤖 GridBot está listo para operar con varios tokens")
    else:
        print(f"\n❌ No se pudo completar la configuración")

if __name__ == "__main__":
    main() 