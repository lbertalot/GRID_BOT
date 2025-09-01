#!/usr/bin/env python3
"""
Script para optimizar la configuración con datos actuales del mercado
"""

import os
import sys
import json
import math
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def calculate_optimal_ranges(current_price, volatility_percent=5):
    """Calcula rangos óptimos basados en el precio actual"""
    min_price = current_price * (1 - volatility_percent / 100)
    max_price = current_price * (1 + volatility_percent / 100)
    return min_price, max_price

def calculate_optimal_quantity(balance, price, min_notional=10, commission_rate=0.001):
    """Calcula cantidad óptima considerando comisiones y mínimos"""
    # Considerar comisión de 0.1% (0.001)
    # Mínimo notional de $10
    if balance <= 0:
        return 0
    
    # Valor disponible después de comisiones
    available_value = balance * price * (1 - commission_rate)
    
    if available_value < min_notional:
        return 0
    
    # Cantidad que cumple el mínimo notional
    min_quantity = min_notional / price
    
    # Usar el 80% del balance disponible para dejar margen
    optimal_quantity = balance * 0.8
    
    return max(min_quantity, optimal_quantity)

def optimize_configuration():
    """Optimiza la configuración con datos actuales"""
    try:
        print("🚀 Optimizando configuración con datos actuales...")
        
        # Cargar datos actuales
        with open("current_market_data.json", "r") as f:
            data = json.load(f)
        
        prices = data["prices"]
        balances = data["balances"]
        total_value = data["total_value"]
        
        print(f"📊 Precios actuales y saldos cargados")
        print(f"💰 Valor total del portafolio: ${total_value:.2f}")
        
        # Configuración optimizada
        optimized_config = {}
        
        # Parámetros de optimización
        volatility_percent = 3  # 3% de volatilidad para rangos más ajustados
        min_notional = 10  # Mínimo $10 por orden
        commission_rate = 0.001  # 0.1% de comisión
        
        # Mapeo de activos
        asset_mapping = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT", 
            "BNB": "BNBUSDT",
            "SPK": "SPKUSDT",
            "ADA": "ADAUSDT",
            "DOT": "DOTUSDT",
            "LINK": "LINKUSDT",
            "MATIC": "MATICUSDT",
            "AVAX": "AVAXUSDT"
        }
        
        print("\n🔧 Optimizando configuración por activo:")
        
        for asset, symbol in asset_mapping.items():
            if symbol in prices and asset in balances:
                current_price = prices[symbol]
                balance = balances[asset]
                
                # Calcular rangos óptimos
                min_price, max_price = calculate_optimal_ranges(current_price, volatility_percent)
                
                # Calcular cantidad óptima
                optimal_quantity = calculate_optimal_quantity(balance, current_price, min_notional, commission_rate)
                
                # Determinar número de grids basado en el rango
                price_range = max_price - min_price
                grid_size = price_range / 5  # 5 grids por defecto
                
                # Ajustar grids según el rango
                if price_range < current_price * 0.02:  # Rango muy pequeño
                    grids = 3
                elif price_range < current_price * 0.05:  # Rango pequeño
                    grids = 5
                else:  # Rango normal
                    grids = 7
                
                # Calcular valor de inversión
                investment_value = optimal_quantity * current_price
                
                # Determinar si está activo
                is_active = investment_value >= min_notional
                
                config = {
                    "symbol": symbol,
                    "min_price": round(min_price, 4),
                    "max_price": round(max_price, 4),
                    "grids": grids,
                    "quantity": round(optimal_quantity, 8),
                    "last_action": None,
                    "is_active": is_active,
                    "investment_amount": round(investment_value, 2),
                    "max_orders": min(grids, 5)  # Máximo 5 órdenes por activo
                }
                
                optimized_config[symbol] = config
                
                status = "✅ ACTIVO" if is_active else "⛔ INACTIVO"
                print(f"   {symbol}: {status}")
                print(f"      Precio actual: ${current_price:.4f}")
                print(f"      Rango: ${min_price:.4f} - ${max_price:.4f}")
                print(f"      Cantidad: {optimal_quantity:.8f}")
                print(f"      Grids: {grids}")
                print(f"      Inversión: ${investment_value:.2f}")
                print()
        
        # Metadata actualizada
        metadata = {
            "optimized_at": datetime.now().isoformat(),
            "optimization_version": "v2.5-market-optimized",
            "source_data": "current_market_data.json",
            "total_portfolio_value": total_value,
            "optimization_parameters": {
                "volatility_percent": volatility_percent,
                "min_notional": min_notional,
                "commission_rate": commission_rate,
                "grid_strategy": "adaptive"
            },
            "market_conditions": {
                "optimization_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_assets": len(optimized_config),
                "active_assets": sum(1 for config in optimized_config.values() if isinstance(config, dict) and config.get("is_active", False)),
                "total_investment": sum(config["investment_amount"] for config in optimized_config.values() if isinstance(config, dict) and config.get("is_active", False))
            },
            "risk_management": {
                "max_daily_loss": 2.0,
                "stop_loss_percent": 5.0,
                "take_profit_percent": 8.0,
                "max_concurrent_orders": 25,
                "commission_aware": True,
                "min_profit_after_commission": 0.5
            }
        }
        
        optimized_config["_optimization_metadata"] = metadata
        
        # Guardar configuración optimizada
        with open("grid_config_optimized_market.json", "w") as f:
            json.dump(optimized_config, f, indent=2)
        
        print("✅ Configuración optimizada guardada en grid_config_optimized_market.json")
        
        # Resumen
        active_configs = [config for config in optimized_config.values() if isinstance(config, dict) and config.get("is_active", False)]
        total_investment = sum(config["investment_amount"] for config in active_configs)
        
        print(f"\n📊 RESUMEN DE OPTIMIZACIÓN:")
        print(f"   Activos activos: {len(active_configs)}/{len(optimized_config)}")
        print(f"   Inversión total: ${total_investment:.2f}")
        print(f"   Valor portafolio: ${total_value:.2f}")
        print(f"   Porcentaje invertido: {(total_investment/total_value)*100:.1f}%")
        
        return optimized_config
        
    except Exception as e:
        print(f"❌ Error optimizando configuración: {e}")
        return None

if __name__ == "__main__":
    optimize_configuration()
