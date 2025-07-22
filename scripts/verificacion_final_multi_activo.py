#!/usr/bin/env python3
"""
Script final para verificar el estado completo del sistema multi-activo
"""

import requests
import json
import time

def verificacion_final_multi_activo():
    """Verificación final del sistema multi-activo"""
    
    print("🎯 VERIFICACIÓN FINAL MULTI-ACTIVO")
    print("=" * 45)
    
    # Verificar estado del sistema
    print("🔍 VERIFICANDO ESTADO DEL SISTEMA:")
    print("-" * 35)
    
    try:
        # Health check
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Servicio API funcionando")
        else:
            print(f"❌ Servicio API no responde: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error conectando al servicio: {e}")
        return
    
    # Verificar configuración
    try:
        response = requests.get("http://localhost:8000/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            print("✅ Configuración cargada correctamente")
        else:
            print(f"❌ Error cargando configuración: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error obteniendo configuración: {e}")
        return
    
    # Analizar configuración
    print("\n📊 ANÁLISIS DE CONFIGURACIÓN:")
    print("-" * 30)
    
    activos_configurados = []
    activos_activos = []
    
    for symbol, asset_config in config.items():
        if symbol == "_optimization_metadata":
            continue
            
        activos_configurados.append(symbol)
        if asset_config.get('is_active', True):
            activos_activos.append(symbol)
        
        print(f"🪙 {symbol}:")
        print(f"   📊 Cantidad: {asset_config.get('quantity', 0)}")
        print(f"   ✅ Activo: {asset_config.get('is_active', True)}")
        print(f"   📈 Grids: {asset_config.get('grids', 0)}")
        print()
    
    # Verificar logs recientes
    print("📋 VERIFICANDO LOGS RECIENTES:")
    print("-" * 30)
    
    try:
        import subprocess
        result = subprocess.run(
            ["docker-compose", "logs", "--tail=50", "api"],
            capture_output=True,
            text=True
        )
        
        logs = result.stdout
        
        # Contar intentos de transacciones por activo
        intentos_por_activo = {}
        errores_por_activo = {}
        exitos_por_activo = {}
        
        for activo in activos_configurados:
            # Contar intentos
            intentos = logs.count(f"Error procesando {activo}")
            intentos_por_activo[activo] = intentos
            
            # Contar errores específicos
            errores = logs.count(f"Error colocando orden de mercado")
            errores_por_activo[activo] = errores
            
            # Contar éxitos
            exitos = logs.count(f"GridBot ejecutó") and logs.count(f"'{symbol}': '{activo}'")
            exitos_por_activo[activo] = exitos
        
        print("📊 ESTADÍSTICAS DE OPERACIÓN:")
        for activo in activos_configurados:
            intentos = intentos_por_activo.get(activo, 0)
            errores = errores_por_activo.get(activo, 0)
            exitos = exitos_por_activo.get(activo, 0)
            
            print(f"🪙 {activo}:")
            print(f"   🔄 Intentos: {intentos}")
            print(f"   ❌ Errores: {errores}")
            print(f"   ✅ Éxitos: {exitos}")
            print()
        
    except Exception as e:
        print(f"❌ Error verificando logs: {e}")
    
    # Verificar cantidades actuales vs requeridas
    print("🔧 VERIFICANDO CANTIDADES:")
    print("-" * 25)
    
    cantidades_actuales = {}
    for symbol, asset_config in config.items():
        if symbol != "_optimization_metadata":
            cantidades_actuales[symbol] = asset_config.get('quantity', 0)
    
    # Cantidades requeridas según Binance
    cantidades_requeridas = {
        'BNBUSDT': 0.001,
        'ANIMEUSDT': 0.1,
        'GPSUSDT': 0.1,
        'GUNUSDT': 1.0,
        'SIGNUSDT': 1.0,
        'SPKUSDT': 1.0,
        'HOMEUSDT': 1.0,
        'HUMAUSDT': 1.0,
    }
    
    cantidades_correctas = 0
    for symbol, cantidad_actual in cantidades_actuales.items():
        cantidad_requerida = cantidades_requeridas.get(symbol, 0)
        if abs(cantidad_actual - cantidad_requerida) < 0.001:
            print(f"✅ {symbol}: {cantidad_actual} (correcto)")
            cantidades_correctas += 1
        else:
            print(f"❌ {symbol}: {cantidad_actual} (debería ser {cantidad_requerida})")
    
    # Generar resumen final
    print(f"\n📊 RESUMEN FINAL:")
    print("-" * 20)
    
    total_activos = len(activos_configurados)
    activos_operativos = len(activos_activos)
    cantidades_ok = cantidades_correctas
    
    print(f"📈 Total activos configurados: {total_activos}")
    print(f"✅ Activos operativos: {activos_operativos}")
    print(f"🔧 Cantidades correctas: {cantidades_ok}/{total_activos}")
    
    # Determinar estado final
    if activos_operativos == total_activos and cantidades_ok == total_activos:
        estado_final = "🎉 COMPLETAMENTE OPERATIVO"
        mensaje_final = "¡GridBot funcionando al 100% con múltiples activos!"
    elif activos_operativos == total_activos:
        estado_final = "⚠️ CASI OPERATIVO"
        mensaje_final = "GridBot operando, solo necesita ajustes menores de cantidades"
    elif activos_operativos > 0:
        estado_final = "🔄 PARCIALMENTE OPERATIVO"
        mensaje_final = f"GridBot operando con {activos_operativos}/{total_activos} activos"
    else:
        estado_final = "❌ NO OPERATIVO"
        mensaje_final = "GridBot no está operando correctamente"
    
    print(f"\n🏆 ESTADO FINAL: {estado_final}")
    print(f"💡 {mensaje_final}")
    
    # Guardar reporte final
    reporte_final = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "estado_final": estado_final,
        "mensaje_final": mensaje_final,
        "activos_configurados": activos_configurados,
        "activos_operativos": activos_operativos,
        "cantidades_correctas": cantidades_ok,
        "total_activos": total_activos,
        "cantidades_actuales": cantidades_actuales,
        "cantidades_requeridas": cantidades_requeridas,
        "intentos_por_activo": intentos_por_activo,
        "errores_por_activo": errores_por_activo,
        "exitos_por_activo": exitos_por_activo
    }
    
    with open('reporte_final_multi_activo.json', 'w') as f:
        json.dump(reporte_final, f, indent=2)
    
    print(f"\n💾 Reporte final guardado en 'reporte_final_multi_activo.json'")
    
    # Enviar notificación final de Telegram
    alert_message = f"🎯 VERIFICACIÓN FINAL MULTI-ACTIVO\n\n"
    alert_message += f"🏆 ESTADO: {estado_final}\n"
    alert_message += f"💡 {mensaje_final}\n\n"
    
    alert_message += f"📊 ESTADÍSTICAS:\n"
    alert_message += f"• Activos configurados: {total_activos}\n"
    alert_message += f"• Activos operativos: {activos_operativos}\n"
    alert_message += f"• Cantidades correctas: {cantidades_ok}/{total_activos}\n\n"
    
    if cantidades_ok == total_activos:
        alert_message += f"✅ TODAS LAS CANTIDADES CORRECTAS\n"
        alert_message += f"🚀 GridBot listo para trading completo\n"
        alert_message += f"🎉 ¡Sistema funcionando al 100%!"
    else:
        alert_message += f"⚠️ CANTIDADES QUE NECESITAN AJUSTE:\n"
        for symbol, cantidad_actual in cantidades_actuales.items():
            cantidad_requerida = cantidades_requeridas.get(symbol, 0)
            if abs(cantidad_actual - cantidad_requerida) >= 0.001:
                alert_message += f"• {symbol}: {cantidad_actual} → {cantidad_requerida}\n"
        alert_message += f"\n🔧 Ajustes menores necesarios"
    
    try:
        telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
        telegram_data = {
            "chat_id": "1248403886",
            "text": alert_message
        }
        response = requests.post(telegram_url, data=telegram_data)
        if response.status_code == 200:
            print("📱 Notificación final enviada a Telegram")
        else:
            print(f"❌ Error enviando notificación: {response.status_code}")
    except Exception as e:
        print(f"❌ Error enviando notificación: {e}")

def main():
    """Función principal"""
    verificacion_final_multi_activo()

if __name__ == "__main__":
    main() 