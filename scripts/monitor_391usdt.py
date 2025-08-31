#!/usr/bin/env python3
"""
Script de monitoreo para balance de 391.75 USDT
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar el directorio app al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

async def monitor_391usdt_balance():
    """Monitorea el balance de 391.75 USDT"""
    try:
        from core.balance_optimizer import balance_optimizer
        from core.commission_aware_trading import commission_aware_trading
        
        print("💰 Monitoreo de Balance 391.75 USDT")
        print("=" * 50)
        
        # Obtener estado del optimizador
        status = balance_optimizer.get_status_report()
        
        print(f"📊 Estado del Balance:")
        print(f"   Balance total: ${status['total_balance']:.2f}")
        print(f"   Reserva: ${status['reserve_amount']:.2f}")
        print(f"   Disponible: ${status['available_amount']:.2f}")
        print(f"   Usado: ${status['total_used']:.2f}")
        print(f"   Libre: ${status['total_available']:.2f}")
        print()
        
        print("📈 Asignaciones por Símbolo:")
        for symbol, alloc in status['allocations'].items():
            print(f"   {symbol}:")
            print(f"     Asignado: ${alloc['allocated']:.2f}")
            print(f"     Usado: ${alloc['used']:.2f}")
            print(f"     Disponible: ${alloc['available']:.2f}")
            print(f"     Máx órdenes: {alloc['max_orders']}")
            print()
        
        # Verificar si hay problemas
        if status['total_used'] > status['available_amount'] * 0.9:
            print("⚠️ ADVERTENCIA: Uso de balance cercano al límite")
        
        if status['total_available'] < 20:
            print("⚠️ ADVERTENCIA: Balance disponible muy bajo")
        
        print("✅ Monitoreo completado")
        
    except Exception as e:
        print(f"❌ Error en monitoreo: {e}")

if __name__ == "__main__":
    asyncio.run(monitor_391usdt_balance())
