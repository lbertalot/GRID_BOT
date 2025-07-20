#!/usr/bin/env python3
"""
Script para analizar pares de trading y calcular distribución conservadora
"""

import requests
import json

def analyze_trading_pairs():
    """Analiza los pares de trading disponibles y sus requisitos mínimos"""
    
    print("🔍 Analizando pares de trading disponibles...")
    
    # Obtener información de exchange
    try:
        response = requests.get("https://api.binance.com/api/v3/exchangeInfo")
        exchange_info = response.json()
        
        # Pares principales que queremos analizar
        target_pairs = [
            "BNBUSDT", "BTCUSDT", "ETHUSDT", "ADAUSDT", 
            "DOTUSDT", "LINKUSDT", "LTCUSDT", "XRPUSDT"
        ]
        
        pairs_info = {}
        
        for symbol_info in exchange_info['symbols']:
            symbol = symbol_info['symbol']
            if symbol in target_pairs and symbol_info['status'] == 'TRADING':
                # Extraer filtros importantes
                lot_size_filter = None
                notional_filter = None
                
                for filter_info in symbol_info['filters']:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        lot_size_filter = filter_info
                    elif filter_info['filterType'] == 'NOTIONAL':
                        notional_filter = filter_info
                
                pairs_info[symbol] = {
                    'baseAsset': symbol_info['baseAsset'],
                    'quoteAsset': symbol_info['quoteAsset'],
                    'lotSize': lot_size_filter,
                    'notional': notional_filter
                }
        
        # Obtener precios actuales
        print("\n📊 Obteniendo precios actuales...")
        prices = {}
        for symbol in pairs_info.keys():
            try:
                response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
                price_data = response.json()
                prices[symbol] = float(price_data['price'])
            except Exception as e:
                print(f"   ❌ Error obteniendo precio de {symbol}: {e}")
        
        # Calcular requisitos mínimos
        print("\n🎯 Calculando requisitos mínimos...")
        min_requirements = {}
        
        for symbol, info in pairs_info.items():
            if symbol in prices:
                price = prices[symbol]
                min_qty = float(info['lotSize']['minQty']) if info['lotSize'] else 0.001
                min_notional = float(info['notional']['minNotional']) if info['notional'] else 5.0
                
                # Calcular cantidad mínima que cumple ambos requisitos
                min_qty_by_notional = min_notional / price
                actual_min_qty = max(min_qty, min_qty_by_notional)
                
                # Ajustar al step size
                step_size = float(info['lotSize']['stepSize']) if info['lotSize'] else 0.001
                adjusted_min_qty = round(actual_min_qty / step_size) * step_size
                
                min_value_usd = adjusted_min_qty * price
                
                min_requirements[symbol] = {
                    'symbol': symbol,
                    'baseAsset': info['baseAsset'],
                    'price': price,
                    'minQuantity': adjusted_min_qty,
                    'minValueUSD': min_value_usd,
                    'stepSize': step_size
                }
        
        return min_requirements, prices
        
    except Exception as e:
        print(f"❌ Error analizando pares: {e}")
        return {}, {}

def calculate_conservative_allocation(ars_balance, min_requirements):
    """Calcula una distribución conservadora del balance en ARS"""
    
    print(f"\n💰 Calculando distribución conservadora...")
    print(f"   Balance ARS: ${ars_balance:,.2f}")
    
    # Convertir ARS a USD (aproximadamente 1 USD = 1000 ARS)
    usd_rate = 1000  # Tasa aproximada ARS/USD
    usd_equivalent = ars_balance / usd_rate
    
    print(f"   Equivalente USD: ${usd_equivalent:.2f}")
    
    # Distribución conservadora (máximo 70% del balance)
    max_investment = usd_equivalent * 0.7
    print(f"   Inversión máxima (70%): ${max_investment:.2f}")
    
    # Seleccionar pares que cumplan con el presupuesto
    affordable_pairs = []
    for symbol, req in min_requirements.items():
        if req['minValueUSD'] <= max_investment * 0.3:  # Máximo 30% por par
            affordable_pairs.append(req)
    
    # Ordenar por valor mínimo (más conservador primero)
    affordable_pairs.sort(key=lambda x: x['minValueUSD'])
    
    # Calcular distribución
    allocation = []
    remaining_budget = max_investment
    
    for pair in affordable_pairs[:4]:  # Máximo 4 pares
        # Usar 20% del presupuesto por par
        investment = min(remaining_budget * 0.2, pair['minValueUSD'] * 1.5)
        quantity = investment / pair['price']
        
        # Ajustar al step size
        step_size = pair['stepSize']
        adjusted_quantity = round(quantity / step_size) * step_size
        final_investment = adjusted_quantity * pair['price']
        
        allocation.append({
            'symbol': pair['symbol'],
            'baseAsset': pair['baseAsset'],
            'quantity': adjusted_quantity,
            'investmentUSD': final_investment,
            'investmentARS': final_investment * usd_rate
        })
        
        remaining_budget -= final_investment
    
    return allocation

def main():
    """Función principal"""
    
    # Balance en ARS (del resultado anterior)
    ars_balance = 300599.6
    
    # Analizar pares de trading
    min_requirements, prices = analyze_trading_pairs()
    
    if not min_requirements:
        print("❌ No se pudieron obtener los requisitos mínimos")
        return
    
    # Mostrar requisitos mínimos
    print("\n📋 Requisitos mínimos por par:")
    for symbol, req in min_requirements.items():
        print(f"   {symbol}:")
        print(f"     💰 Cantidad mínima: {req['minQuantity']:.6f} {req['baseAsset']}")
        print(f"     💵 Valor mínimo: ${req['minValueUSD']:.2f}")
        print(f"     📊 Precio actual: ${req['price']:.2f}")
    
    # Calcular distribución conservadora
    allocation = calculate_conservative_allocation(ars_balance, min_requirements)
    
    # Mostrar distribución
    print("\n🎯 Distribución conservadora recomendada:")
    total_investment_ars = 0
    
    for item in allocation:
        print(f"\n   📊 {item['symbol']}:")
        print(f"      💰 Cantidad: {item['quantity']:.6f} {item['baseAsset']}")
        print(f"      💵 Inversión: ${item['investmentUSD']:.2f} USD")
        print(f"      🇦🇷 Inversión: ${item['investmentARS']:,.2f} ARS")
        total_investment_ars += item['investmentARS']
    
    print(f"\n💰 Resumen:")
    print(f"   Total inversión: ${total_investment_ars:,.2f} ARS")
    print(f"   Porcentaje del balance: {(total_investment_ars/ars_balance)*100:.1f}%")
    print(f"   Balance restante: ${(ars_balance - total_investment_ars):,.2f} ARS")
    
    # Guardar configuración
    config = {
        'allocation': allocation,
        'total_investment_ars': total_investment_ars,
        'balance_remaining_ars': ars_balance - total_investment_ars
    }
    
    with open('conservative_grid_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 Configuración guardada en 'conservative_grid_config.json'")

if __name__ == "__main__":
    main() 