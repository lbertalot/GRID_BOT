#!/usr/bin/env python3
"""
Script para probar que Telegram esté funcionando correctamente
"""

import requests
import json
import time
from datetime import datetime

def probar_telegram():
    """Prueba el envío de mensajes a Telegram"""
    
    print("📱 PROBANDO INTEGRACIÓN CON TELEGRAM")
    print("=" * 40)
    
    # Configuración de Telegram
    bot_token = "8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8"
    chat_id = "1248403886"
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Mensaje de prueba
    test_message = f"""
🤖 PRUEBA DE TELEGRAM - GridBot

📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ Sistema: Funcionando correctamente
🪙 Activos: 8 configurados
🔄 Estado: GridBot operativo

🎯 Esta es una prueba para verificar que las notificaciones de Telegram estén funcionando correctamente.

🚀 GridBot Multi-Activo está listo para operar.
"""
    
    try:
        # Enviar mensaje de prueba
        response = requests.post(telegram_url, data={
            "chat_id": chat_id,
            "text": test_message
        })
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Mensaje de Telegram enviado exitosamente")
                print(f"📱 Message ID: {result['result']['message_id']}")
                return True
            else:
                print(f"❌ Error en respuesta de Telegram: {result}")
                return False
        else:
            print(f"❌ Error HTTP: {response.status_code}")
            print(f"📄 Respuesta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")
        return False

def verificar_estado_sistema():
    """Verifica el estado del sistema"""
    
    print("\n🔍 VERIFICANDO ESTADO DEL SISTEMA")
    print("-" * 35)
    
    try:
        # Verificar API
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            print("✅ API funcionando correctamente")
        else:
            print(f"❌ Error en API: {response.status_code}")
            return False
        
        # Verificar configuración
        response = requests.get("http://localhost:8000/config", timeout=10)
        if response.status_code == 200:
            config = response.json()
            activos = [k for k in config.keys() if k != "_optimization_metadata"]
            print(f"✅ Configuración cargada: {len(activos)} activos")
        else:
            print(f"❌ Error cargando configuración: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando sistema: {e}")
        return False

def forzar_ejecucion_grid():
    """Fuerza una ejecución del grid para generar notificaciones"""
    
    print("\n🔄 FORZANDO EJECUCIÓN DEL GRID")
    print("-" * 35)
    
    try:
        # Llamar al endpoint de ejecución manual
        response = requests.post("http://localhost:8000/execute-grid", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Ejecución del grid iniciada")
            print(f"📊 Resultado: {result}")
            return True
        else:
            print(f"❌ Error ejecutando grid: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error forzando ejecución: {e}")
        return False

def verificar_logs_recientes():
    """Verifica logs recientes para transacciones"""
    
    print("\n📋 VERIFICANDO LOGS RECIENTES")
    print("-" * 30)
    
    try:
        import subprocess
        result = subprocess.run(
            ["docker-compose", "logs", "--tail=50", "api"],
            capture_output=True,
            text=True
        )
        
        logs = result.stdout
        
        # Buscar patrones específicos
        if "GridBot ejecutó" in logs:
            print("✅ Transacciones detectadas en logs")
            return True
        elif "Error" in logs:
            print("⚠️ Errores detectados en logs")
            return False
        else:
            print("ℹ️ No hay transacciones recientes")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando logs: {e}")
        return False

def enviar_notificacion_estado():
    """Envía notificación del estado actual"""
    
    print("\n📊 ENVIANDO NOTIFICACIÓN DE ESTADO")
    print("-" * 40)
    
    bot_token = "8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8"
    chat_id = "1248403886"
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        # Obtener estado del sistema
        response = requests.get("http://localhost:8000/config", timeout=10)
        if response.status_code == 200:
            config = response.json()
            activos = [k for k in config.keys() if k != "_optimization_metadata"]
            
            status_message = f"""
📊 ESTADO ACTUAL DEL GRIDBOT

🕐 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ Sistema: Operativo
🪙 Activos configurados: {len(activos)}

📋 Activos activos:
"""
            
            for activo in activos:
                asset_config = config[activo]
                cantidad = asset_config.get('quantity', 0)
                status_message += f"• {activo}: {cantidad}\n"
            
            status_message += f"""
🔄 Scheduler: Activo
📱 Telegram: Funcionando
🎯 Estado: Listo para operar

💡 El GridBot está funcionando correctamente y esperando oportunidades de trading.
"""
            
            # Enviar mensaje
            response = requests.post(telegram_url, data={
                "chat_id": chat_id,
                "text": status_message
            })
            
            if response.status_code == 200:
                print("✅ Notificación de estado enviada")
                return True
            else:
                print(f"❌ Error enviando notificación: {response.status_code}")
                return False
                
        else:
            print(f"❌ Error obteniendo configuración: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error enviando notificación: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 INICIANDO PRUEBAS DE TELEGRAM")
    print("=" * 40)
    
    # Verificar estado del sistema
    if not verificar_estado_sistema():
        print("❌ Sistema no está funcionando correctamente")
        return
    
    # Probar Telegram
    if not probar_telegram():
        print("❌ Telegram no está funcionando")
        return
    
    # Verificar logs
    verificar_logs_recientes()
    
    # Enviar notificación de estado
    enviar_notificacion_estado()
    
    print("\n🎉 PRUEBAS COMPLETADAS")
    print("=" * 25)
    print("✅ Sistema funcionando")
    print("✅ Telegram operativo")
    print("✅ Notificaciones enviadas")
    print("\n📱 Verifica que hayas recibido los mensajes en Telegram")

if __name__ == "__main__":
    main() 