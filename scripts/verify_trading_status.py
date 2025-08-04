#!/usr/bin/env python3
"""
Script para verificar el estado actual del sistema de trading
Explica por qué no se ejecutan operaciones y qué se necesita para que funcione
"""

import os
import json
import asyncio
from typing import Dict, Any
from app.services.binance_credentials import test_binance_connection, get_binance_client_with_verification
from app.core.optimized_grid_manager import create_optimized_grid_manager


async def verify_trading_status():
    """Verifica el estado completo del sistema de trading"""
    
    print("🔍 VERIFICACIÓN DEL ESTADO DEL SISTEMA DE TRADING")
    print("=" * 60)
    
    # 1. Verificar credenciales de Binance
    print("\n1️⃣ VERIFICANDO CREDENCIALES DE BINANCE")
    print("-" * 40)
    
    try:
        connection_valid = test_binance_connection()
        if connection_valid:
            print("✅ Credenciales de Binance válidas")
            
            # Obtener información de la cuenta
            testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
            client, verification_info = get_binance_client_with_verification(testnet)
            
            account_info = verification_info.get('account_info', {})
            balances = account_info.get('balances', [])
            
            # Mostrar balances relevantes
            relevant_assets = ['BTC', 'ETH', 'SPK', 'USDT', 'BNB']
            print(f"\n💰 BALANCES RELEVANTES:")
            for balance in balances:
                asset = balance['asset']
                free = float(balance['free'])
                if asset in relevant_assets and free > 0:
                    print(f"   • {asset}: {free}")
            
        else:
            print("❌ Credenciales de Binance inválidas")
            return
    except Exception as e:
        print(f"❌ Error verificando credenciales: {e}")
        return
    
    # 2. Verificar configuración de trading
    print("\n2️⃣ VERIFICANDO CONFIGURACIÓN DE TRADING")
    print("-" * 40)
    
    try:
        config_file = "grid_config_optimized.json"
        if not os.path.exists(config_file):
            print(f"❌ Archivo de configuración no encontrado: {config_file}")
            return
        
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        print(f"✅ Archivo de configuración cargado: {config_file}")
        
        # Mostrar activos configurados
        print(f"\n📊 ACTIVOS CONFIGURADOS:")
        for symbol, config in config_data.items():
            if symbol != "_optimization_metadata":
                print(f"   • {symbol}:")
                print(f"     - Cantidad: {config.get('quantity')}")
                print(f"     - Rango: {config.get('min_price')} - {config.get('max_price')}")
                print(f"     - Activo: {config.get('is_active')}")
        
        # Verificar min_notional
        metadata = config_data.get("_optimization_metadata", {})
        min_notional = metadata.get("min_notional", 10.0)
        print(f"\n💰 MIN_NOTIONAL CONFIGURADO: {min_notional} USDT")
        
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")
        return
    
    # 3. Verificar saldos vs requerimientos
    print("\n3️⃣ ANÁLISIS DE SALDOS VS REQUERIMIENTOS")
    print("-" * 40)
    
    try:
        # Obtener balances actuales
        balances_dict = {}
        for balance in balances:
            asset = balance['asset']
            free = float(balance['free'])
            if free > 0:
                balances_dict[asset] = free
        
        print("📋 COMPARACIÓN DE SALDOS:")
        insufficient_assets = []
        
        for symbol, config in config_data.items():
            if symbol == "_optimization_metadata":
                continue
                
            base_asset = symbol.replace("USDT", "")
            required_quantity = config.get('quantity', 0)
            current_balance = balances_dict.get(base_asset, 0)
            
            print(f"\n   🔸 {symbol}:")
            print(f"      - Saldo actual: {current_balance} {base_asset}")
            print(f"      - Cantidad requerida: {required_quantity} {base_asset}")
            
            if current_balance >= required_quantity:
                print(f"      ✅ SALDO SUFICIENTE")
            else:
                missing = required_quantity - current_balance
                print(f"      ❌ SALDO INSUFICIENTE - Faltan {missing} {base_asset}")
                insufficient_assets.append(symbol)
        
        # 4. Recomendaciones
        print("\n4️⃣ RECOMENDACIONES")
        print("-" * 40)
        
        if insufficient_assets:
            print("❌ PROBLEMA IDENTIFICADO:")
            print("   Los siguientes activos no tienen saldo suficiente para operar:")
            for symbol in insufficient_assets:
                print(f"   • {symbol}")
            
            print("\n💡 SOLUCIONES POSIBLES:")
            print("   1. Comprar los activos faltantes en Binance")
            print("   2. Modificar la configuración para usar activos disponibles")
            print("   3. Reducir las cantidades en la configuración")
            
            # Mostrar USDT disponible
            usdt_balance = balances_dict.get('USDT', 0)
            if usdt_balance > 0:
                print(f"\n💰 USDT DISPONIBLE: {usdt_balance}")
                print("   Puedes usar este USDT para comprar los activos faltantes")
                
                # Calcular costos aproximados
                print("\n💸 COSTOS APROXIMADOS PARA COMPRAR:")
                for symbol in insufficient_assets:
                    config = config_data.get(symbol, {})
                    required_quantity = config.get('quantity', 0)
                    min_price = config.get('min_price', 0)
                    estimated_cost = required_quantity * min_price
                    print(f"   • {symbol}: ~{estimated_cost:.2f} USDT")
        else:
            print("✅ TODOS LOS ACTIVOS TIENEN SALDO SUFICIENTE")
            print("   El sistema debería poder ejecutar operaciones")
        
        # 5. Estado del sistema
        print("\n5️⃣ ESTADO DEL SISTEMA")
        print("-" * 40)
        
        paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"
        testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
        
        print(f"   • Modo Paper Trading: {'✅ ACTIVADO' if paper_trading else '❌ DESACTIVADO'}")
        print(f"   • Testnet: {'✅ ACTIVADO' if testnet else '❌ DESACTIVADO'}")
        print(f"   • Credenciales: ✅ VÁLIDAS")
        print(f"   • Configuración: ✅ CARGADA")
        
        if insufficient_assets:
            print(f"   • Saldos: ❌ INSUFICIENTES ({len(insufficient_assets)} activos)")
            print(f"   • Estado: ⏸️ SISTEMA LISTO PERO SIN SALDO SUFICIENTE")
        else:
            print(f"   • Saldos: ✅ SUFICIENTES")
            print(f"   • Estado: 🚀 SISTEMA LISTO PARA OPERAR")
        
    except Exception as e:
        print(f"❌ Error analizando saldos: {e}")


if __name__ == "__main__":
    asyncio.run(verify_trading_status()) 