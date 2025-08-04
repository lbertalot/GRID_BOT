#!/usr/bin/env python3
"""
Script de monitoreo de balances para ejecución automática via cron
"""

import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def monitor_balances():
    """Monitorea los balances de la cuenta de Binance"""
    try:
        print(f"🕐 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando monitoreo de balances...")
        
        from app.core.optimized_grid_manager import create_optimized_grid_manager
        from app.services.fund_manager import fund_manager
        
        # Crear manager
        manager = await create_optimized_grid_manager('grid_config_optimized.json')
        if not manager:
            print("❌ No se pudo crear el manager")
            return
        
        # Obtener balances
        balances = await manager.get_asset_balances()
        
        # Obtener resumen de trading
        trading_summary = await fund_manager.get_trading_summary(balances)
        
        # Mostrar información básica
        usdt_balance = balances.get('USDT', 0)
        btc_balance = balances.get('BTC', 0)
        eth_balance = balances.get('ETH', 0)
        spk_balance = balances.get('SPK', 0)
        
        print(f"💰 Balances principales:")
        print(f"   USDT: ${usdt_balance:.2f}")
        print(f"   BTC: {btc_balance:.6f}")
        print(f"   ETH: {eth_balance:.6f}")
        print(f"   SPK: {spk_balance:.2f}")
        
        # Verificar capacidad de trading
        can_trade = trading_summary.get('can_trade', False)
        max_trades = trading_summary.get('max_trades_possible', 0)
        
        print(f"📊 Estado de trading:")
        print(f"   Puede operar: {'✅ Sí' if can_trade else '❌ No'}")
        print(f"   Operaciones posibles: {max_trades}")
        
        # Alertas si es necesario
        if usdt_balance < 10:
            print(f"⚠️ ALERTA: Saldo USDT bajo (${usdt_balance:.2f})")
        
        if not can_trade:
            print(f"⚠️ ALERTA: Sistema no puede operar")
        
        print(f"✅ Monitoreo completado - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ Error en monitoreo de balances: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(monitor_balances()) 