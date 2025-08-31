#!/usr/bin/env python3
"""
Script para probar el sistema de comisiones de Binance
"""

import asyncio
import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.commission_manager import commission_manager
from app.services.binance_service import BinanceService
from app.services.fund_manager import fund_manager

async def test_commission_calculations():
    """Probar cálculos de comisiones"""
    print("🧪 Probando cálculos de comisiones...")
    
    # Configurar datos de prueba
    test_cases = [
        {
            "symbol": "BTCUSDT",
            "quantity": 0.001,
            "price": 45000,
            "side": "BUY",
            "order_type": "MARKET"
        },
        {
            "symbol": "ETHUSDT", 
            "quantity": 0.01,
            "price": 3000,
            "side": "SELL",
            "order_type": "MARKET"
        },
        {
            "symbol": "BNBUSDT",
            "quantity": 0.1,
            "price": 500,
            "side": "BUY",
            "order_type": "LIMIT"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📊 Test Case {i}: {test_case['symbol']}")
        
        # Calcular comisión
        notional_value = test_case['quantity'] * test_case['price']
        commission = commission_manager.calculate_commission(
            notional_value, test_case['order_type'], test_case['symbol']
        )
        
        print(f"   Cantidad: {test_case['quantity']}")
        print(f"   Precio: ${test_case['price']:,.2f}")
        print(f"   Valor notional: ${notional_value:,.2f}")
        print(f"   Comisión: ${commission:.6f} USDT")
        print(f"   Porcentaje: {(commission/notional_value*100):.4f}%")

async def test_profit_calculations():
    """Probar cálculos de ganancia con comisiones"""
    print("\n💰 Probando cálculos de ganancia con comisiones...")
    
    # Simular operaciones de compra y venta
    buy_price = 45000
    sell_price = 46000  # 2.22% de ganancia bruta
    quantity = 0.001
    
    profit_data = commission_manager.calculate_profit_with_commissions(
        buy_price, sell_price, quantity, 'MARKET', 'MARKET', 'BTCUSDT'
    )
    
    print(f"📈 Análisis de ganancia para BTCUSDT:")
    print(f"   Precio de compra: ${buy_price:,.2f}")
    print(f"   Precio de venta: ${sell_price:,.2f}")
    print(f"   Cantidad: {quantity}")
    print(f"   Ganancia bruta: ${profit_data['gross_profit']:.6f}")
    print(f"   Comisión de compra: ${profit_data['buy_commission']:.6f}")
    print(f"   Comisión de venta: ${profit_data['sell_commission']:.6f}")
    print(f"   Comisión total: ${profit_data['total_commission']:.6f}")
    print(f"   Ganancia neta: ${profit_data['net_profit']:.6f}")
    print(f"   Porcentaje neto: {profit_data['profit_percentage']:.4f}%")

async def test_grid_profitability():
    """Probar validación de rentabilidad de grid trading"""
    print("\n🔍 Probando validación de rentabilidad de grid...")
    
    # Configuración de grid de prueba
    grid_config = {
        "symbol": "BTCUSDT",
        "min_price": 44000,
        "max_price": 46000,
        "quantity": 0.001,
        "num_levels": 5,
        "min_profit_percentage": 0.5
    }
    
    binance_service = BinanceService()
    analysis = binance_service.validate_grid_profitability(
        grid_config["symbol"],
        grid_config["min_price"],
        grid_config["max_price"],
        grid_config["quantity"],
        grid_config["num_levels"],
        grid_config["min_profit_percentage"]
    )
    
    print(f"📊 Análisis de rentabilidad de grid:")
    print(f"   Símbolo: {grid_config['symbol']}")
    print(f"   Rango de precios: ${grid_config['min_price']:,.2f} - ${grid_config['max_price']:,.2f}")
    print(f"   Niveles: {grid_config['num_levels']}")
    print(f"   Cantidad por nivel: {grid_config['quantity']}")
    print(f"   Es rentable: {analysis['is_profitable']}")
    print(f"   Tasa de rentabilidad: {analysis['profitability_rate']:.1f}%")
    print(f"   Niveles rentables: {analysis['profitable_levels']}/{analysis['total_levels']}")
    print(f"   Ganancia total estimada: ${analysis['total_net_profit']:.6f}")
    print(f"   Comisión total: ${analysis['total_commission']:.6f}")
    print(f"   Recomendación: {analysis['recommendation']}")

async def test_fund_validation():
    """Probar validación de fondos con comisiones"""
    print("\n💳 Probando validación de fondos con comisiones...")
    
    # Simular balances
    balances = {
        "USDT": 100.0,
        "BTC": 0.001,
        "ETH": 0.01
    }
    
    # Probar validación de compra
    is_valid, message, details = await fund_manager.validate_trade_requirements(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.001,
        price=45000,
        balances=balances,
        order_type="MARKET"
    )
    
    print(f"📋 Validación de compra BTCUSDT:")
    print(f"   Es válida: {is_valid}")
    print(f"   Mensaje: {message}")
    if details:
        print(f"   Valor notional: ${details.get('notional_value', 0):,.2f}")
        print(f"   Comisión: ${details.get('commission_usdt', 0):.6f}")
        print(f"   Porcentaje de comisión: {details.get('commission_percentage', 0):.4f}%")

async def test_commission_rates():
    """Probar obtención de tasas de comisión"""
    print("\n📊 Probando obtención de tasas de comisión...")
    
    # Obtener tasas por defecto
    default_rates = commission_manager.get_commission_rates()
    print(f"Tasas por defecto:")
    print(f"   Maker: {default_rates['maker']:.4f} ({default_rates['maker']*100:.2f}%)")
    print(f"   Taker: {default_rates['taker']:.4f} ({default_rates['taker']*100:.2f}%)")
    
    # Obtener tasas para símbolo específico
    btc_rates = commission_manager.get_commission_rates("BTCUSDT")
    print(f"Tasas para BTCUSDT:")
    print(f"   Maker: {btc_rates['maker']:.4f} ({btc_rates['maker']*100:.2f}%)")
    print(f"   Taker: {btc_rates['taker']:.4f} ({btc_rates['taker']*100:.2f}%)")

async def main():
    """Función principal"""
    print("🚀 Iniciando pruebas del sistema de comisiones...")
    
    try:
        # Actualizar tasas de comisión
        print("🔄 Actualizando tasas de comisión desde Binance...")
        commission_manager._update_commission_rates()
        
        # Ejecutar pruebas
        await test_commission_rates()
        await test_commission_calculations()
        await test_profit_calculations()
        await test_grid_profitability()
        await test_fund_validation()
        
        print("\n✅ Todas las pruebas completadas exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
