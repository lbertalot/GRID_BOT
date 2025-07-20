#!/usr/bin/env python3
"""
Script simple para probar alertas de Telegram
"""

import os
from dotenv import load_dotenv
from app.services.telegram_alert import send_telegram_alert

def main():
    """Prueba las alertas de Telegram"""
    print("🤖 Probando Alertas de Telegram...")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Mensaje de prueba
    test_message = """
🎉 ¡Alertas de Telegram Configuradas!

✅ GridBot está enviando notificaciones:
• Órdenes ejecutadas
• Ganancias realizadas  
• Errores de API
• Cambios de balance
• Operaciones de grid

📊 Estado actual:
💰 Balance: 68.59 USDT + 0.00997 BNB
🎯 Grid Trading: BNBUSDT activo
📱 Alertas: Funcionando correctamente

🤖 GridBot está monitoreado 24/7
"""
    
    # Enviar mensaje
    success = send_telegram_alert(test_message)
    
    if success:
        print("✅ Alerta enviada correctamente")
        print("📱 Revisa tu Telegram")
    else:
        print("❌ Error al enviar alerta")
    
    return success

if __name__ == "__main__":
    main() 