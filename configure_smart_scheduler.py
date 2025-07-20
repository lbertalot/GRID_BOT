#!/usr/bin/env python3
"""
Script para configurar el scheduler de manera inteligente
"""

import requests
import json
import time
import math

def get_current_balance():
    """Obtiene el balance actual"""
    
    try:
        response = requests.get("http://localhost:8000/api/trade/balances")
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"❌ Error obteniendo balance: {e}")
        return None

def configure_smart_grid():
    """Configura el grid de manera inteligente basado en el balance"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🧠 Configurando Grid Inteligente...")
    
    # Obtener balance actual
    balances = get_current_balance()
    if not balances:
        print("   ❌ No se pudo obtener el balance")
        return False
    
    print(f"   💰 Balance actual:")
    for asset, amount in balances.items():
        if asset in ['USDT', 'BNB', 'BTC', 'LTC', 'LINK', 'DOT'] and float(amount) > 0:
            print(f"      • {asset}: {amount}")
    
    # Determinar la mejor estrategia basada en el balance
    usdt_balance = float(balances.get('USDT', 0))
    bnb_balance = float(balances.get('BNB', 0))
    
    if bnb_balance >= 0.05:
        # Usar BNBUSDT si tenemos suficiente BNB
        symbol = "BNBUSDT"
        raw_quantity = min(0.01, bnb_balance * 0.1)  # Usar máximo 10% del balance
        # Ajustar a la precisión requerida (stepSize 0.001)
        quantity = round(math.floor(raw_quantity / 0.001) * 0.001, 6)
        print(f"   📊 Estrategia: BNBUSDT con {quantity} BNB")
    elif usdt_balance >= 10:
        # Comprar BNB si tenemos USDT
        symbol = "BNBUSDT"
        quantity = 0.008  # Cantidad ajustada a stepSize
        print(f"   📊 Estrategia: Comprar BNB con USDT")
    else:
        print(f"   ❌ Balance insuficiente para trading")
        return False
    
    # Obtener precio actual
    try:
        response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
        current_price = float(response.json()['price'])
        
        # Calcular rangos conservadores (±5%)
        min_price = round(current_price * 0.95, 2)
        max_price = round(current_price * 1.05, 2)
        
        print(f"   📈 Precio actual: ${current_price:.2f}")
        print(f"   📊 Rango: ${min_price:.2f} - ${max_price:.2f}")
        
        # Configurar grid
        grid_config = {
            "symbol": symbol,
            "min_price": min_price,
            "max_price": max_price,
            "grids": 8,
            "quantity": quantity
        }
        
        # Actualizar configuración del scheduler
        response = requests.post(
            f"{base_url}/api/trade/grid_config",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=grid_config
        )
        
        if response.status_code == 200:
            print(f"   ✅ Grid configurado exitosamente")
            
            # Enviar alerta de Telegram
            alert_message = f"🧠 Grid Inteligente Configurado\n\n"
            alert_message += f"📊 Símbolo: {symbol}\n"
            alert_message += f"💰 Cantidad: {quantity}\n"
            alert_message += f"📈 Rango: ${min_price:.2f} - ${max_price:.2f}\n"
            alert_message += f"🔗 Grids: 8\n\n"
            alert_message += f"💡 Basado en balance disponible"
            
            try:
                telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
                telegram_data = {
                    "chat_id": "1248403886",
                    "text": alert_message
                }
                requests.post(telegram_url, data=telegram_data)
                print(f"   📱 Alerta enviada a Telegram")
            except Exception as e:
                print(f"   ❌ Error enviando alerta: {e}")
            
            return True
        else:
            print(f"   ❌ Error configurando grid: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error obteniendo precio: {e}")
        return False

def main():
    """Función principal"""
    
    print("🎯 Configurando Scheduler Inteligente")
    print("=" * 45)
    
    success = configure_smart_grid()
    
    if success:
        print(f"\n🎉 Scheduler inteligente configurado!")
        print(f"📊 El sistema ahora:")
        print(f"   • Verifica balance antes de ejecutar")
        print(f"   • Usa cantidades conservadoras")
        print(f"   • Se adapta al balance disponible")
        print(f"   • Evita errores de balance insuficiente")
    else:
        print(f"\n❌ Error configurando scheduler")

if __name__ == "__main__":
    main() 