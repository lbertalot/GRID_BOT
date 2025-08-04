#!/usr/bin/env python3
"""
Script para probar el FundManager
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def test_fund_manager():
    """Prueba el FundManager con datos reales"""
    try:
        print("🧪 Probando FundManager")
        print("=" * 40)
        
        from app.services.fund_manager import fund_manager
        from app.services.binance_client_singleton import binance_client_singleton
        
        # Obtener balances reales
        print("💰 Obteniendo balances reales...")
        balances = binance_client_singleton.get_balances()
        
        # Mostrar balances importantes
        important_assets = ['USDT', 'BTC', 'ETH', 'BNB']
        print("\n📊 Balances actuales:")
        for asset in important_assets:
            if asset in balances:
                print(f"   {asset}: {balances[asset]}")
        
        # Probar validaciones
        print("\n🔍 Probando validaciones de trades:")
        
        # Test 1: Compra de BTC
        symbol = "BTCUSDT"
        side = "BUY"
        quantity = 0.0001
        price = 114000.0
        
        print(f"\n📈 Test 1: {side} {quantity} {symbol} @ ${price}")
        is_valid, message, adjusted_quantity = fund_manager.validate_trade_requirements(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            balances=balances
        )
        
        print(f"   ✅ Válido: {is_valid}")
        print(f"   📝 Mensaje: {message}")
        if adjusted_quantity:
            print(f"   🔄 Cantidad ajustada: {adjusted_quantity}")
        
        # Test 2: Venta de BTC
        side = "SELL"
        print(f"\n📉 Test 2: {side} {quantity} {symbol} @ ${price}")
        is_valid, message, adjusted_quantity = fund_manager.validate_trade_requirements(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            balances=balances
        )
        
        print(f"   ✅ Válido: {is_valid}")
        print(f"   📝 Mensaje: {message}")
        if adjusted_quantity:
            print(f"   🔄 Cantidad ajustada: {adjusted_quantity}")
        
        # Test 3: Compra con cantidad grande (debería fallar)
        quantity_large = 1.0
        print(f"\n🚨 Test 3: {side} {quantity_large} {symbol} @ ${price} (cantidad grande)")
        is_valid, message, adjusted_quantity = fund_manager.validate_trade_requirements(
            symbol=symbol,
            side=side,
            quantity=quantity_large,
            price=price,
            balances=balances
        )
        
        print(f"   ✅ Válido: {is_valid}")
        print(f"   📝 Mensaje: {message}")
        if adjusted_quantity:
            print(f"   🔄 Cantidad ajustada: {adjusted_quantity}")
        
        print("\n🎉 Pruebas del FundManager completadas")
        
    except Exception as e:
        print(f"❌ Error en pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fund_manager()) 