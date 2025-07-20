#!/usr/bin/env python3
"""
Script para ejecutar automáticamente todos los grids conservadores
"""

import requests
import json
import time

def run_grid_trading(symbol, min_price, max_price, quantity, base_url, api_key):
    """Ejecuta grid trading para un símbolo específico"""
    
    print(f"\n🔄 Ejecutando grid para {symbol}...")
    
    grid_params = {
        "symbol": symbol,
        "min_price": min_price,
        "max_price": max_price,
        "grids": 8,
        "quantity": quantity
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/trade/run_grid",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=grid_params
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'order_result' in result:
                order = result['order_result']
                action = result['decision']['action']
                executed_qty = order['executedQty']
                quote_qty = order['cummulativeQuoteQty']
                
                print(f"   ✅ Grid ejecutado exitosamente")
                print(f"      🔄 Acción: {action}")
                print(f"      💰 Cantidad: {executed_qty}")
                print(f"      💵 Valor: ${quote_qty}")
                print(f"      📋 Orden ID: {order['orderId']}")
                return True
            else:
                print(f"   ⏸️  No se ejecutó orden (sin acción requerida)")
                return True
        else:
            error = response.json()
            print(f"   ❌ Error ejecutando grid: {error.get('message', 'Error desconocido')}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error en la solicitud: {e}")
        return False

def main():
    """Función principal"""
    
    # Configuración
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🎯 Ejecutando Grids Conservadores Automáticamente")
    print("=" * 55)
    
    # Cargar configuración de grids activos
    try:
        with open('active_grids_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ No se encontró el archivo 'active_grids_config.json'")
        print("   Ejecuta primero 'setup_conservative_grids.py'")
        return
    
    active_grids = config['active_grids']
    
    print(f"📋 Ejecutando {len(active_grids)} grids...")
    print(f"💰 Inversión total: ${config['total_investment_ars']:,.2f} ARS")
    
    # Verificar balance antes de ejecutar
    try:
        response = requests.get(f"{base_url}/api/trade/balances")
        balances = response.json()
        print(f"\n💰 Balance actual:")
        for asset in ['USDT', 'BNB', 'LTC', 'LINK', 'DOT']:
            if asset in balances:
                print(f"   • {asset}: {balances[asset]}")
    except Exception as e:
        print(f"❌ Error obteniendo balance: {e}")
    
    # Ejecutar cada grid
    successful_grids = []
    
    for item in active_grids:
        symbol = item['symbol']
        quantity = item['quantity']
        
        # Obtener precios actuales para calcular rangos
        try:
            price_response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
            current_price = float(price_response.json()['price'])
            
            # Calcular rangos conservadores (±5%)
            min_price = round(current_price * 0.95, 2)
            max_price = round(current_price * 1.05, 2)
            
            success = run_grid_trading(symbol, min_price, max_price, quantity, base_url, api_key)
            if success:
                successful_grids.append(item)
            
        except Exception as e:
            print(f"   ❌ Error obteniendo precio para {symbol}: {e}")
            continue
        
        # Pausa entre grids
        time.sleep(2)
    
    # Resumen
    print(f"\n🎉 Resumen de ejecución:")
    print(f"   ✅ Grids ejecutados: {len(successful_grids)}/{len(active_grids)}")
    
    if successful_grids:
        print(f"\n📊 Grids exitosos:")
        for item in successful_grids:
            print(f"   • {item['symbol']}: {item['quantity']:.6f} {item['baseAsset']}")
        
        # Verificar balance final
        try:
            response = requests.get(f"{base_url}/api/trade/balances")
            final_balances = response.json()
            print(f"\n💰 Balance final:")
            for asset in ['USDT', 'BNB', 'LTC', 'LINK', 'DOT']:
                if asset in final_balances:
                    print(f"   • {asset}: {final_balances[asset]}")
        except Exception as e:
            print(f"❌ Error obteniendo balance final: {e}")
        
        # Enviar alerta de Telegram
        alert_message = f"🎯 Grids Conservadores Ejecutados\n\n"
        alert_message += f"📊 Grids exitosos: {len(successful_grids)}/{len(active_grids)}\n"
        alert_message += f"💰 Inversión: ${config['total_investment_ars']:,.2f} ARS\n\n"
        
        for item in successful_grids:
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