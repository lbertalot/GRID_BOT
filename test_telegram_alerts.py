#!/usr/bin/env python3
"""
Script para probar todas las alertas de Telegram de GridBot
"""

import os
import sys
from dotenv import load_dotenv
from app.services.telegram_alert import send_telegram_alert
import time

def test_telegram_alerts():
    """Prueba todas las alertas de Telegram"""
    print("🤖 Probando Alertas de Telegram para GridBot")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Verificar configuración
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Configuración de Telegram no encontrada")
        print("Verifica TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env")
        return False
    
    print(f"✅ Bot Token: {token[:20]}...")
    print(f"✅ Chat ID: {chat_id}")
    print()
    
    # Lista de alertas a probar
    alerts = [
        {
            "title": "🚀 Inicio de GridBot",
            "message": "🤖 GridBot iniciado correctamente\n\n📊 Monitoreando operaciones\n💰 Balance: 68.59 USDT\n🎯 Estrategia: Grid Trading BNBUSDT"
        },
        {
            "title": "✅ Orden Ejecutada",
            "message": "✅ Orden ejecutada: BUY 0.014 BNBUSDT (MARKET)\n💰 Precio: $732.88\n💵 Valor: $10.26 USDT"
        },
        {
            "title": "📈 Ganancia Realizada",
            "message": "📈 Ganancia realizada: +$2.45 USDT\n🎯 Símbolo: BNBUSDT\n📊 Profit: +3.2%"
        },
        {
            "title": "⚠️ Alerta de Balance",
            "message": "⚠️ Balance bajo detectado\n💰 USDT: 15.23\n🔴 Recomendación: Depositar fondos"
        },
        {
            "title": "❌ Error de API",
            "message": "❌ Error ejecutando orden: BUY 0.014 BNBUSDT\n🔍 Código: -2010\n💡 Insufficient balance"
        },
        {
            "title": "🔄 Grid Trading",
            "message": "🤖 GridBot ejecutó SELL 0.014 BNBUSDT a 732.88\n📊 Nivel: 703.39\n💰 Ganancia: +$0.42"
        },
        {
            "title": "📊 Resumen Diario",
            "message": "📊 Resumen del día:\n✅ Órdenes: 12\n💰 Ganancia: +$8.45\n📈 ROI: +2.1%\n🎯 Estado: Activo"
        }
    ]
    
    # Enviar alertas de prueba
    for i, alert in enumerate(alerts, 1):
        print(f"📱 Enviando alerta {i}/{len(alerts)}: {alert['title']}")
        
        success = send_telegram_alert(alert['message'])
        
        if success:
            print(f"✅ Enviada correctamente")
        else:
            print(f"❌ Error al enviar")
        
        # Esperar 2 segundos entre mensajes
        time.sleep(2)
        print()
    
    # Mensaje final
    final_message = """
🎉 ¡Prueba de Alertas Completada!

✅ Todas las alertas configuradas:
• Inicio de GridBot
• Órdenes ejecutadas
• Ganancias realizadas
• Alertas de balance
• Errores de API
• Operaciones de grid
• Resúmenes diarios

📱 Recibirás notificaciones en tiempo real
🤖 GridBot está monitoreado 24/7
"""
    
    print("📱 Enviando mensaje final...")
    success = send_telegram_alert(final_message)
    
    if success:
        print("✅ Mensaje final enviado")
    else:
        print("❌ Error al enviar mensaje final")
    
    print("\n🎯 Configuración de Alertas Completada!")
    print("📱 Revisa tu Telegram para ver todas las alertas")
    
    return True

def send_custom_alert():
    """Envía una alerta personalizada"""
    print("\n📝 Enviar alerta personalizada:")
    message = input("Escribe tu mensaje: ")
    
    if message:
        success = send_telegram_alert(message)
        if success:
            print("✅ Mensaje enviado correctamente")
        else:
            print("❌ Error al enviar mensaje")
    else:
        print("❌ Mensaje vacío")

def main():
    """Función principal"""
    print("🤖 Configurador de Alertas Telegram - GridBot")
    print("=" * 50)
    
    while True:
        print("\nOpciones:")
        print("1. Probar todas las alertas")
        print("2. Enviar alerta personalizada")
        print("3. Salir")
        
        choice = input("\nSelecciona una opción (1-3): ")
        
        if choice == "1":
            test_telegram_alerts()
        elif choice == "2":
            send_custom_alert()
        elif choice == "3":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción inválida")

if __name__ == "__main__":
    main() 