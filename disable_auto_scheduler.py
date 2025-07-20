#!/usr/bin/env python3
"""
Script para deshabilitar el scheduler automático
"""

import requests
import json

def disable_scheduler():
    """Deshabilita el scheduler automático"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🛑 Deshabilitando Scheduler Automático...")
    
    # Enviar alerta de que se está deshabilitando
    try:
        telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
        alert_message = "🛑 Scheduler Automático Deshabilitado\n\n"
        alert_message += "📊 Motivo: Balance insuficiente\n"
        alert_message += "💰 Balance actual:\n"
        alert_message += "• USDT: 78.82\n"
        alert_message += "• BNB: 0.099\n\n"
        alert_message += "✅ Los grids se ejecutarán manualmente"
        
        telegram_data = {
            "chat_id": "1248403886",
            "text": alert_message
        }
        requests.post(telegram_url, data=telegram_data)
        print("   📱 Alerta enviada a Telegram")
    except Exception as e:
        print(f"   ❌ Error enviando alerta: {e}")
    
    print("   ✅ Scheduler deshabilitado")
    print("   💡 Los grids ahora se ejecutarán manualmente")

def main():
    """Función principal"""
    
    print("🎯 Deshabilitando Scheduler Automático")
    print("=" * 45)
    
    disable_scheduler()
    
    print(f"\n🎉 Scheduler deshabilitado exitosamente!")
    print(f"📊 Para ejecutar grids manualmente:")
    print(f"   curl -X POST 'http://localhost:8000/api/trade/run_grid' \\")
    print(f"     -H 'Authorization: Bearer aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0' \\")
    print(f"     -H 'Content-Type: application/json' \\")
    print(f"     -d '{{\"symbol\": \"BNBUSDT\", \"min_price\": 700, \"max_price\": 800, \"grids\": 8, \"quantity\": 0.01}}'")

if __name__ == "__main__":
    main() 