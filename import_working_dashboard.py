#!/usr/bin/env python3
"""
Script para importar el dashboard funcional de GridBot
"""

import subprocess
import json
import time

def import_dashboard():
    """Importa el dashboard funcional"""
    
    print("🎯 Importando Dashboard Funcional de GridBot")
    print("=" * 50)
    
    # 1. Verificar que Grafana esté disponible
    print("🔍 Verificando Grafana...")
    try:
        result = subprocess.run([
            "curl", "-s", "http://localhost:3000/api/health"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Grafana está disponible")
        else:
            print("   ❌ Grafana no está disponible")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 2. Importar dashboard
    print("📊 Importando dashboard...")
    
    try:
        # Leer el archivo JSON
        with open('working_dashboard.json', 'r') as f:
            dashboard_data = json.load(f)
        
        # Convertir a string para curl
        dashboard_json = json.dumps(dashboard_data)
        
        # Importar usando curl con credenciales correctas
        result = subprocess.run([
            "curl", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-u", "admin:gridbot123",
            "-d", dashboard_json,
            "http://localhost:3000/api/dashboards/db"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            response = json.loads(result.stdout)
            if 'url' in response:
                dashboard_url = f"http://localhost:3000{response['url']}"
                print(f"   ✅ Dashboard importado exitosamente!")
                print(f"   🔗 URL: {dashboard_url}")
                print(f"   🆔 UID: {response.get('uid', 'N/A')}")
                
                # Enviar alerta de Telegram
                send_telegram_alert(dashboard_url)
                return True
            else:
                print(f"   ❌ Error en la respuesta: {result.stdout}")
                return False
        else:
            print(f"   ❌ Error en la importación: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def send_telegram_alert(dashboard_url):
    """Envía alerta de Telegram"""
    try:
        alert_message = "🎯 Dashboard de GridBot Funcional\n\n"
        alert_message += "📊 URL: " + dashboard_url + "\n"
        alert_message += "👤 Usuario: admin\n"
        alert_message += "🔑 Contraseña: gridbot123\n\n"
        alert_message += "📈 Métricas disponibles:\n"
        alert_message += "• Estado del sistema\n"
        alert_message += "• Conexión Binance\n"
        alert_message += "• Uso de CPU y memoria\n"
        alert_message += "• Llamadas API Binance\n"
        alert_message += "• Latencia API\n\n"
        alert_message += "🔄 Actualización: cada 30 segundos"
        
        telegram_data = {
            "chat_id": "1248403886",
            "text": alert_message
        }
        
        subprocess.run([
            "curl", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(telegram_data),
            "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
        ], capture_output=True)
        
        print("   📱 Alerta enviada a Telegram")
    except Exception as e:
        print(f"   ❌ Error enviando alerta: {e}")

def main():
    """Función principal"""
    
    success = import_dashboard()
    
    if success:
        print(f"\n🎉 ¡Dashboard configurado exitosamente!")
        print(f"\n📋 Instrucciones:")
        print(f"   1. Ve a http://localhost:3000")
        print(f"   2. Inicia sesión con admin/gridbot123")
        print(f"   3. Busca 'GridBot Trading Dashboard'")
        print(f"   4. O ve a Dashboards → Browse")
        print(f"\n📊 Métricas que verás:")
        print(f"   • Estado del sistema (ONLINE/OFFLINE)")
        print(f"   • Conexión Binance (CONNECTED/DISCONNECTED)")
        print(f"   • Uso de CPU y memoria")
        print(f"   • Llamadas API Binance")
        print(f"   • Latencia de API")
    else:
        print(f"\n❌ Error en la configuración del dashboard")

if __name__ == "__main__":
    main() 