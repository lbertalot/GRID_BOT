#!/usr/bin/env python3
"""
Script para verificar que el sistema está en modo real
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def verify_real_mode():
    """Verifica que el sistema esté en modo real"""
    try:
        print("🔍 Verificación de Modo Real")
        print("=" * 40)
        
        # Verificar variables de entorno
        paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"
        testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        
        print(f"📄 Modo Paper Trading: {'Activado' if paper_trading else 'Desactivado'}")
        print(f"🌐 Testnet: {'Activado' if testnet else 'Desactivado'}")
        
        if not paper_trading and not testnet:
            print("\n✅ SISTEMA EN MODO REAL")
            print("💰 Las operaciones se ejecutarán con dinero real")
            print("⚠️  ¡PRECAUCIÓN! Se usarán fondos reales de tu cuenta")
        else:
            print("\n❌ SISTEMA NO EN MODO REAL")
            if paper_trading:
                print("📄 Paper Trading está activado")
            if testnet:
                print("🌐 Testnet está activado")
        
        # Verificar credenciales
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        
        print(f"\n🔐 Credenciales:")
        print(f"• API Key: {'✅ Configurada' if api_key else '❌ No configurada'}")
        print(f"• API Secret: {'✅ Configurada' if api_secret else '❌ No configurada'}")
        
        if not paper_trading and not testnet and api_key and api_secret:
            print("\n🎯 RESUMEN:")
            print("✅ Sistema configurado para trading real")
            print("✅ Credenciales de Binance configuradas")
            print("✅ Conectando a Binance Mainnet")
            print("\n🚀 El bot está listo para operar con dinero real")
        else:
            print("\n⚠️  El sistema no está completamente configurado para trading real")
            
    except Exception as e:
        print(f"❌ Error en verificación: {e}")

if __name__ == "__main__":
    asyncio.run(verify_real_mode()) 