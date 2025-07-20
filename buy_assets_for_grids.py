#!/usr/bin/env python3
"""
Script para comprar activos necesarios para los grids
"""

import requests
import json
import time

def get_current_price(symbol):
    """Obtiene el precio actual de un símbolo"""
    try:
        response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
        price_data = response.json()
        return float(price_data['price'])
    except Exception as e:
        print(f"❌ Error obteniendo precio de {symbol}: {e}")
        return None

def buy_asset(symbol, quantity, base_url, api_key):
    """Compra un activo específico"""
    
    print(f"\n🛒 Comprando {quantity} {symbol}...")
    
    # Obtener precio actual
    current_price = get_current_price(symbol)
    if not current_price:
        print(f"   ❌ No se pudo obtener precio para {symbol}")
        return False
    
    estimated_value = quantity * current_price
    print(f"   📊 Precio actual: ${current_price:.2f}")
    print(f"   💰 Cantidad: {quantity}")
    print(f"   💵 Valor estimado: ${estimated_value:.2f}")
    
    # Realizar compra
    order_data = {
        "symbol": symbol,
        "side": "BUY",
        "quantity": quantity,
        "type": "MARKET"
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/trade/order",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=order_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Compra exitosa")
            if 'order' in result and 'cummulativeQuoteQty' in result['order']:
                actual_value = float(result['order']['cummulativeQuoteQty'])
                print(f"      💵 Valor real: ${actual_value:.2f}")
            return True
        else:
            error = response.json()
            print(f"   ❌ Error en la compra: {error.get('message', 'Error desconocido')}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error en la solicitud: {e}")
        return False

def main():
    """Función principal"""
    
    # Configuración
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🛒 Comprando Activos para Grids Conservadores")
    print("=" * 50)
    
    # Cargar configuración del análisis anterior
    try:
        with open('conservative_grid_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ No se encontró el archivo 'conservative_grid_config.json'")
        print("   Ejecuta primero 'analyze_trading_pairs.py'")
        return
    
    allocation = config['allocation']
    
    # Verificar balance USDT
    try:
        response = requests.get(f"{base_url}/api/trade/balances")
        balances = response.json()
        usdt_balance = balances.get('USDT', 0)
        print(f"💰 Balance USDT disponible: ${usdt_balance:.2f}")
    except Exception as e:
        print(f"❌ Error obteniendo balance: {e}")
        return
    
    # Filtrar solo los pares que necesitamos comprar (excluir BNBUSDT)
    assets_to_buy = [item for item in allocation if item['symbol'] != 'BNBUSDT']
    
    print(f"📋 Comprando {len(assets_to_buy)} activos...")
    
    # Comprar cada activo
    successful_purchases = []
    total_spent = 0
    
    for item in assets_to_buy:
        symbol = item['symbol']
        quantity = item['quantity']
        estimated_cost = item['investmentUSD']
        
        # Verificar si tenemos suficiente USDT
        if estimated_cost > usdt_balance * 0.8:  # Máximo 80% del balance
            print(f"   ⚠️  Saltando {symbol}: Costo estimado (${estimated_cost:.2f}) muy alto")
            continue
        
        success = buy_asset(symbol, quantity, base_url, api_key)
        if success:
            successful_purchases.append(item)
            total_spent += estimated_cost
        
        # Pausa entre compras
        time.sleep(2)
    
    # Resumen
    print(f"\n🎉 Resumen de compras:")
    print(f"   ✅ Compras exitosas: {len(successful_purchases)}/{len(assets_to_buy)}")
    print(f"   💰 Total gastado: ~${total_spent:.2f}")
    
    if successful_purchases:
        print(f"\n📊 Activos comprados:")
        for item in successful_purchases:
            print(f"   • {item['symbol']}: {item['quantity']:.6f} {item['baseAsset']}")
        
        # Verificar balance final
        try:
            response = requests.get(f"{base_url}/api/trade/balances")
            final_balances = response.json()
            print(f"\n💰 Balance final:")
            for asset in ['USDT', 'BTC', 'LTC', 'LINK', 'DOT', 'BNB']:
                if asset in final_balances:
                    print(f"   • {asset}: {final_balances[asset]}")
        except Exception as e:
            print(f"❌ Error obteniendo balance final: {e}")
        
        # Enviar alerta de Telegram
        alert_message = f"🛒 Compras para Grids Completadas\n\n"
        alert_message += f"📊 Activos comprados: {len(successful_purchases)}\n"
        alert_message += f"💰 Total gastado: ~${total_spent:.2f}\n\n"
        
        for item in successful_purchases:
            alert_message += f"• {item['symbol']}: {item['quantity']:.6f} {item['baseAsset']}\n"
        
        # Enviar alerta
        try:
            telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
            telegram_data = {
                "chat_id": "1248403886",
                "text": alert_message
            }
            requests.post(telegram_url, data=telegram_data)
            print(f"\n📱 Alerta enviada a Telegram")
        except Exception as e:
            print(f"\n❌ Error enviando alerta: {e}")

if __name__ == "__main__":
    main() 