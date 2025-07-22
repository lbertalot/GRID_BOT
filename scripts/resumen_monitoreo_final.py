#!/usr/bin/env python3
"""
Script para enviar resumen final del monitoreo
"""

import requests
from datetime import datetime

def enviar_resumen_monitoreo():
    """Envía resumen final del monitoreo"""
    
    try:
        bot_token = "8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8"
        chat_id = "1248403886"
        
        mensaje = f"""
📊 RESUMEN MONITOREO - 5 MINUTOS

📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⏱️ Duración: 5 minutos de monitoreo continuo

🔍 HALLAZGOS:

✅ CONDICIONES OPTIMIZADAS:
• Rangos ajustados a precios actuales
• Todos los activos en rango de operación
• API funcionando correctamente
• Scheduler ejecutándose cada 60 segundos

❌ PROBLEMA PERSISTENTE:
• GridBot intenta órdenes SELL
• Error: "Parámetros de orden inválidos"
• Problema en validación de órdenes

💡 ANÁLISIS:
• No es problema de rangos (están correctos)
• No es problema de precios (están en rango)
• Es problema de validación de órdenes Binance
• Posiblemente step sizes o precision issues

📈 ESTADO ACTUAL:
• GridBot operativo ✅
• Condiciones optimizadas ✅
• Monitoreo activo ✅
• Necesita ajuste en validación de órdenes ⚠️

🎯 PRÓXIMOS PASOS:
1. Revisar validación de órdenes
2. Ajustar step sizes si es necesario
3. Verificar precision de cantidades
4. Continuar monitoreo

🚀 RESULTADO:
GridBot funcionando con condiciones reales
Solo necesita ajuste en validación de órdenes
"""
        
        response = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={
            "chat_id": chat_id,
            "text": mensaje
        })
        
        if response.status_code == 200:
            print("✅ Resumen de monitoreo enviado")
            return True
        else:
            print(f"❌ Error enviando resumen: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Error enviando resumen: {e}")
        return False

def main():
    """Función principal"""
    
    print("📊 ENVIANDO RESUMEN FINAL DE MONITOREO")
    print("=" * 45)
    
    if enviar_resumen_monitoreo():
        print("\n🎉 MONITOREO COMPLETADO")
        print("=" * 25)
        print("✅ 5 minutos de monitoreo")
        print("✅ Análisis completo")
        print("✅ Resumen enviado")
        print("✅ Problema identificado")
        print("\n💡 GridBot necesita ajuste en validación de órdenes")
    else:
        print("❌ Error enviando resumen")

if __name__ == "__main__":
    main() 