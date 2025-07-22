#!/usr/bin/env python3
"""
Script rápido para ajustar condiciones de mercado
"""

import requests
import json
from datetime import datetime

def obtener_precios_actuales():
    """Obtiene precios actuales de todos los activos"""
    
    activos = ["BNBUSDT", "ANIMEUSDT", "GPSUSDT", "GUNUSDT", "SIGNUSDT", "SPKUSDT", "HOMEUSDT", "HUMAUSDT"]
    precios = {}
    
    for activo in activos:
        try:
            response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={activo}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                precios[activo] = float(data['price'])
                print(f"✅ {activo}: ${precios[activo]:.6f}")
        except:
            print(f"❌ Error con {activo}")
    
    return precios

def crear_configuracion_ajustada(precios):
    """Crea configuración ajustada a precios actuales"""
    
    nueva_config = {}
    
    for activo, precio in precios.items():
        # Rango del 2% arriba y abajo del precio actual
        rango = 0.02
        min_price = precio * (1 - rango)
        max_price = precio * (1 + rango)
        
        # Cantidades según el activo
        cantidades = {
            "BNBUSDT": 0.001,
            "ANIMEUSDT": 0.1,
            "GPSUSDT": 0.1,
            "GUNUSDT": 1.0,
            "SIGNUSDT": 1.0,
            "SPKUSDT": 1.0,
            "HOMEUSDT": 1.0,
            "HUMAUSDT": 1.0
        }
        
        nueva_config[activo] = {
            'symbol': activo,
            'min_price': round(min_price, 6),
            'max_price': round(max_price, 6),
            'grids': 6,
            'quantity': cantidades.get(activo, 0.1),
            'last_action': None,
            'is_active': True
        }
        
        print(f"🪙 {activo}: ${min_price:.6f} - ${max_price:.6f}")
    
    # Agregar metadatos
    nueva_config['_optimization_metadata'] = {
        "optimized_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "optimization_version": "4.0",
        "ajuste_tipo": "Rangos ajustados a precios actuales"
    }
    
    return nueva_config

def aplicar_configuracion(config):
    """Aplica la nueva configuración"""
    
    # Guardar nueva configuración
    with open('grid_config_optimized.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Configuración aplicada")

def enviar_notificacion():
    """Envía notificación de ajuste"""
    
    bot_token = "8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8"
    chat_id = "1248403886"
    
    mensaje = f"""
🔧 CONDICIONES DE MERCADO AJUSTADAS

📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 Acción: Rangos optimizados a precios actuales

📊 AJUSTES:
• Rangos centrados en precios reales
• 2% arriba y abajo del precio actual
• 6 grids por activo
• Cantidades optimizadas

✅ RESULTADO:
• Condiciones de trading optimizadas
• Sistema listo para ejecutar transacciones
• GridBot operativo con rangos reales

🚀 ¡Listo para operar!
"""
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={
            "chat_id": chat_id,
            "text": mensaje
        })
        if response.status_code == 200:
            print("✅ Notificación enviada")
    except:
        print("❌ Error enviando notificación")

def main():
    print("🎯 AJUSTANDO CONDICIONES DE MERCADO")
    print("=" * 40)
    
    # Obtener precios
    precios = obtener_precios_actuales()
    
    # Crear configuración ajustada
    config = crear_configuracion_ajustada(precios)
    
    # Aplicar configuración
    aplicar_configuracion(config)
    
    # Enviar notificación
    enviar_notificacion()
    
    print("\n🎉 AJUSTE COMPLETADO")
    print("🔄 Reiniciando sistema...")
    
    # Reiniciar sistema
    import subprocess
    subprocess.run(["docker-compose", "restart", "api"])

if __name__ == "__main__":
    main() 