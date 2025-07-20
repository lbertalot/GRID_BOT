#!/usr/bin/env python3
"""
Script para verificar y corregir el estado de conexión con Binance
"""

import os
import sys
import time
from dotenv import load_dotenv
from binance import Client
from binance.exceptions import BinanceAPIException

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.metrics import binance_connection_status
from app.services.binance_service import BinanceService

def check_binance_connection():
    """Verifica y corrige el estado de conexión con Binance"""
    
    print("🔍 Verificando Conexión con Binance")
    print("=" * 40)
    
    # Cargar variables de entorno
    load_dotenv()
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Error: Credenciales de Binance no configuradas")
        print("   Verifica que BINANCE_API_KEY y BINANCE_API_SECRET estén en el archivo .env")
        binance_connection_status.set(0)
        return False
    
    print(f"✅ Credenciales encontradas")
    print(f"   API Key: {api_key[:10]}...")
    
    # Probar conexión directa
    print("\n🔗 Probando conexión directa...")
    try:
        client = Client(api_key, api_secret)
        
        # Probar diferentes endpoints
        tests = [
            ("get_server_time", "Tiempo del servidor"),
            ("get_system_status", "Estado del sistema"),
            ("get_account", "Información de cuenta")
        ]
        
        for method_name, description in tests:
            try:
                print(f"   🔍 Probando {method_name} ({description})...")
                method = getattr(client, method_name)
                result = method()
                print(f"   ✅ {method_name} exitoso")
                
                if method_name == 'get_account':
                    print(f"      Tipo de cuenta: {result.get('accountType', 'N/A')}")
                    print(f"      Trading habilitado: {result.get('canTrade', 'N/A')}")
                    
                    # Mostrar balances principales
                    balances = {b["asset"]: float(b["free"]) for b in result["balances"] if float(b["free"]) > 0}
                    if balances:
                        print(f"      Balances disponibles: {balances}")
                    else:
                        print(f"      ⚠️  No hay balances disponibles")
                
            except BinanceAPIException as e:
                print(f"   ❌ {method_name} falló: {e.code} - {e.message}")
                if e.code == -1022:
                    print(f"      🔧 Error de autenticación - Verifica credenciales")
                    binance_connection_status.set(0)
                    return False
            except Exception as e:
                print(f"   ❌ {method_name} error: {e}")
                binance_connection_status.set(0)
                return False
        
        # Si llegamos aquí, la conexión está funcionando
        print(f"\n✅ Conexión con Binance exitosa")
        binance_connection_status.set(1)
        
        # Probar el servicio de Binance
        print(f"\n🔧 Probando servicio de Binance...")
        try:
            binance_service = BinanceService()
            
            # Forzar inicialización
            binance_service._initialize_client()
            
            # Probar métodos del servicio
            account_info = binance_service.get_account_info()
            print(f"   ✅ Servicio de Binance funcionando")
            print(f"      Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
            
            # Verificar métrica
            current_status = binance_connection_status._value.get()
            print(f"      Estado de métrica: {current_status} ({'CONNECTED' if current_status == 1 else 'DISCONNECTED'})")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error en servicio de Binance: {e}")
            binance_connection_status.set(0)
            return False
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        binance_connection_status.set(0)
        return False

def test_metrics_endpoint():
    """Prueba el endpoint de métricas"""
    print(f"\n📊 Probando endpoint de métricas...")
    
    try:
        import requests
        response = requests.get("http://localhost:8000/api/metrics/metrics/")
        
        if response.status_code == 200:
            metrics = response.text
            if "gridbot_binance_connection_status" in metrics:
                print(f"   ✅ Métricas disponibles")
                # Buscar el valor de la métrica
                for line in metrics.split('\n'):
                    if 'gridbot_binance_connection_status' in line and not line.startswith('#'):
                        print(f"      {line.strip()}")
                        break
            else:
                print(f"   ⚠️  Métrica de conexión no encontrada")
        else:
            print(f"   ❌ Error accediendo a métricas: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Función principal"""
    
    print("🎯 Diagnóstico de Conexión Binance")
    print("=" * 50)
    
    # Verificar conexión
    success = check_binance_connection()
    
    # Probar métricas
    test_metrics_endpoint()
    
    if success:
        print(f"\n🎉 ¡Conexión con Binance establecida correctamente!")
        print(f"📊 El dashboard debería mostrar 'CONNECTED' ahora")
        
        # Enviar alerta de Telegram
        try:
            import requests
            telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
            alert_message = "✅ Conexión Binance Restaurada\n\n"
            alert_message += "🔗 Estado: CONNECTED\n"
            alert_message += "📊 Dashboard actualizado\n"
            alert_message += "🤖 GridBot listo para operar"
            
            telegram_data = {
                "chat_id": "1248403886",
                "text": alert_message
            }
            requests.post(telegram_url, data=telegram_data)
            print(f"📱 Alerta enviada a Telegram")
        except Exception as e:
            print(f"❌ Error enviando alerta: {e}")
    else:
        print(f"\n❌ Error en la conexión con Binance")
        print(f"🔧 Verifica:")
        print(f"   1. Credenciales en archivo .env")
        print(f"   2. Estado de la API de Binance")
        print(f"   3. Restricciones de IP")
        print(f"   4. Permisos de la API Key")

if __name__ == "__main__":
    main() 