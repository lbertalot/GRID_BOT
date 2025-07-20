#!/usr/bin/env python3
"""
Script para comprar BNB automáticamente para trading
"""

import requests
import json
import time

def buy_bnb_for_trading():
    """Compra BNB para poder generar transacciones"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🛒 Comprando BNB para Trading")
    print("=" * 40)
    
    # Verificar balance actual
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        usdt_balance = balances.get('USDT', 0)
        bnb_balance = balances.get('BNB', 0)
        
        print(f"💰 Balance actual:")
        print(f"   • USDT: {usdt_balance:.2f}")
        print(f"   • BNB: {bnb_balance:.6f}")
        
        # Calcular cantidad a comprar (usar 10% del USDT disponible)
        usdt_to_spend = min(usdt_balance * 0.1, 15)  # Máximo $15
        estimated_bnb = usdt_to_spend / 735  # Precio aproximado de BNB
        
        print(f"\n📊 Compra planificada:")
        print(f"   • USDT a gastar: ${usdt_to_spend:.2f}")
        print(f"   • BNB estimado: {estimated_bnb:.6f}")
        
        # Confirmar compra
        confirm = input(f"\n¿Confirmar compra de {estimated_bnb:.6f} BNB por ${usdt_to_spend:.2f} USDT? (y/n): ")
        
        if confirm.lower() != 'y':
            print("❌ Compra cancelada")
            return False
        
        # Ejecutar orden de compra
        print(f"\n🔄 Ejecutando orden de compra...")
        
        order_data = {
            "symbol": "BNBUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": round(estimated_bnb, 6)
        }
        
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
            print(f"✅ Compra exitosa!")
            print(f"   • Orden ID: {result.get('orderId', 'N/A')}")
            print(f"   • Cantidad: {estimated_bnb:.6f} BNB")
            print(f"   • Valor: ${usdt_to_spend:.2f} USDT")
            
            # Enviar alerta de Telegram
            alert_message = f"🛒 Compra de BNB Exitosa\n\n"
            alert_message += f"💰 Cantidad: {estimated_bnb:.6f} BNB\n"
            alert_message += f"💵 Valor: ${usdt_to_spend:.2f} USDT\n"
            alert_message += f"📋 Orden ID: {result.get('orderId', 'N/A')}\n\n"
            alert_message += f"🎯 Ahora GridBot puede generar transacciones\n"
            alert_message += f"📱 Recibirás alertas de trading automáticamente"
            
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
            
            return True
            
        else:
            error_msg = response.json().get('message', 'Error desconocido')
            print(f"❌ Error en la compra: {error_msg}")
            
            # Enviar alerta de error
            try:
                telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
                alert_message = f"❌ Error en Compra de BNB\n\n"
                alert_message += f"🔍 Error: {error_msg}\n"
                alert_message += f"💰 USDT disponible: {usdt_balance:.2f}\n"
                alert_message += f"📊 BNB actual: {bnb_balance:.6f}\n\n"
                alert_message += f"💡 Verificar configuración de trading"
                
                telegram_data = {
                    "chat_id": "1248403886",
                    "text": alert_message
                }
                requests.post(telegram_url, data=telegram_data)
            except Exception as e:
                print(f"❌ Error enviando alerta: {e}")
            
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Función principal"""
    success = buy_bnb_for_trading()
    
    if success:
        print(f"\n🎉 ¡BNB comprado exitosamente!")
        print(f"📱 Ahora recibirás alertas de transacciones automáticamente")
        print(f"🤖 GridBot está listo para operar")
    else:
        print(f"\n❌ No se pudo completar la compra")
        print(f"🔧 Verifica el balance y la configuración")

if __name__ == "__main__":
    main() 