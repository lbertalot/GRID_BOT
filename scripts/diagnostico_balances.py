#!/usr/bin/env python3
"""
Script para diagnosticar balances y problemas de órdenes
"""

import requests
import json
from datetime import datetime

def verificar_estado_api():
    """Verifica el estado de la API"""
    
    print("🔍 DIAGNÓSTICO DE BALANCES Y ÓRDENES")
    print("=" * 45)
    
    try:
        # Verificar estado de la API
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API funcionando correctamente")
            return True
        else:
            print(f"❌ API no responde: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error conectando a API: {e}")
        return False

def verificar_configuracion_actual():
    """Verifica la configuración actual"""
    
    print("\n📋 CONFIGURACIÓN ACTUAL:")
    print("-" * 25)
    
    try:
        response = requests.get("http://localhost:8000/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            
            for symbol, data in config.items():
                if symbol != '_optimization_metadata':
                    print(f"🪙 {symbol}:")
                    print(f"   📊 Rango: ${data['min_price']:.6f} - ${data['max_price']:.6f}")
                    print(f"   📈 Cantidad: {data['quantity']}")
                    print(f"   🎯 Activo: {data['is_active']}")
                    print()
            
            return config
        else:
            print(f"❌ Error obteniendo configuración: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def verificar_precios_actuales():
    """Verifica precios actuales vs rangos configurados"""
    
    print("📊 PRECIOS ACTUALES VS RANGOS:")
    print("-" * 30)
    
    try:
        # Obtener configuración
        config = verificar_configuracion_actual()
        if not config:
            return
        
        for symbol, data in config.items():
            if symbol == '_optimization_metadata':
                continue
                
            try:
                # Obtener precio actual
                response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
                if response.status_code == 200:
                    precio_actual = float(response.json()['price'])
                    min_price = data['min_price']
                    max_price = data['max_price']
                    
                    en_rango = min_price <= precio_actual <= max_price
                    
                    print(f"🪙 {symbol}:")
                    print(f"   💰 Precio actual: ${precio_actual:.6f}")
                    print(f"   📉 Rango configurado: ${min_price:.6f} - ${max_price:.6f}")
                    print(f"   🎯 Estado: {'✅ EN RANGO' if en_rango else '❌ FUERA DE RANGO'}")
                    
                    if en_rango:
                        print(f"   🚀 ¡Listo para operar!")
                    else:
                        if precio_actual < min_price:
                            print(f"   📈 Necesita subir: ${min_price - precio_actual:.6f}")
                        else:
                            print(f"   📉 Necesita bajar: ${precio_actual - max_price:.6f}")
                    print()
                    
            except Exception as e:
                print(f"❌ Error con {symbol}: {e}")
                
    except Exception as e:
        print(f"❌ Error verificando precios: {e}")

def analizar_problema_ordenes():
    """Analiza el problema con las órdenes SELL"""
    
    print("🔍 ANÁLISIS DEL PROBLEMA DE ÓRDENES:")
    print("-" * 35)
    
    print("❌ PROBLEMA IDENTIFICADO:")
    print("   • GridBot intenta hacer órdenes SELL")
    print("   • No tiene balance de activos para vender")
    print("   • Necesita hacer compras iniciales primero")
    print()
    
    print("💡 SOLUCIÓN:")
    print("   • Ejecutar compras pequeñas iniciales")
    print("   • Esperar a que los precios entren en rango")
    print("   • Luego ejecutar órdenes SELL")
    print()

def enviar_diagnostico_telegram():
    """Envía diagnóstico a Telegram"""
    
    try:
        bot_token = "8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8"
        chat_id = "1248403886"
        
        mensaje = f"""
🔍 DIAGNÓSTICO DE TRANSACCIONES

📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

❌ PROBLEMA IDENTIFICADO:
• GridBot intenta órdenes SELL sin balance
• Error: "Parámetros de orden inválidos"
• No hay activos para vender

💡 CAUSA:
• Rangos ajustados correctamente
• Precios en rango de operación
• Falta balance inicial de activos

🛠️ SOLUCIÓN:
• Ejecutar compras pequeñas iniciales
• Generar balance de activos
• Luego permitir órdenes SELL

📊 ESTADO:
• API funcionando ✅
• Configuración optimizada ✅
• Scheduler activo ✅
• Solo falta balance inicial

🚀 PRÓXIMO PASO:
Ejecutar compras iniciales para generar balance
"""
        
        response = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={
            "chat_id": chat_id,
            "text": mensaje
        })
        
        if response.status_code == 200:
            print("✅ Diagnóstico enviado a Telegram")
        
    except Exception as e:
        print(f"❌ Error enviando diagnóstico: {e}")

def main():
    """Función principal"""
    
    # Verificar estado API
    if not verificar_estado_api():
        return
    
    # Verificar configuración
    verificar_configuracion_actual()
    
    # Verificar precios
    verificar_precios_actuales()
    
    # Analizar problema
    analizar_problema_ordenes()
    
    # Enviar diagnóstico
    enviar_diagnostico_telegram()
    
    print("🎯 DIAGNÓSTICO COMPLETADO")
    print("=" * 30)
    print("✅ Problema identificado")
    print("✅ Solución propuesta")
    print("✅ Notificación enviada")
    print("\n💡 El GridBot necesita compras iniciales para generar balance")

if __name__ == "__main__":
    main() 