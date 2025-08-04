#!/usr/bin/env python3
"""
Script para probar la detección de señales de grid trading
"""

import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

def test_grid_signals():
    """Prueba la detección de señales con precios actuales"""
    try:
        print("🧪 Probando Detección de Señales de Grid Trading")
        print("=" * 50)
        
        from app.services.grid_strategy import decide_grid_action
        
        # Precios actuales (de los logs)
        current_prices = {
            'BTCUSDT': 114465.34,
            'ETHUSDT': 3550.7,
            'SPKUSDT': 0.123597
        }
        
        # Configuraciones de grid (de la configuración actual)
        grid_configs = {
            'BTCUSDT': {
                'min_price': 114000.0,
                'max_price': 116000.0,
                'grids': 6,
                'levels': [114000.0, 114400.0, 114800.0, 115200.0, 115600.0, 116000.0]
            },
            'ETHUSDT': {
                'min_price': 3540.0,
                'max_price': 3580.0,
                'grids': 6,
                'levels': [3540.0, 3548.0, 3556.0, 3564.0, 3572.0, 3580.0]
            },
            'SPKUSDT': {
                'min_price': 0.095,
                'max_price': 0.125,
                'grids': 8,
                'levels': [0.095, 0.09928571, 0.10357143, 0.10785714, 0.11214286, 0.11642857, 0.12071429, 0.125]
            }
        }
        
        print(f"📊 Análisis de Señales con Nueva Tolerancia (5%):")
        print()
        
        for symbol, price in current_prices.items():
            config = grid_configs[symbol]
            levels = config['levels']
            
            print(f"🪙 {symbol}:")
            print(f"   Precio actual: ${price}")
            print(f"   Rango: ${config['min_price']} - ${config['max_price']}")
            print(f"   Niveles: {len(levels)}")
            
            # Encontrar nivel más cercano
            closest_level = min(levels, key=lambda x: abs(x - price))
            distance = abs(price - closest_level)
            range_size = config['max_price'] - config['min_price']
            tolerance = range_size * 0.05  # 5% de tolerancia
            
            print(f"   📍 Nivel más cercano: ${closest_level}")
            print(f"   📏 Distancia al nivel: ${distance:.6f}")
            print(f"   🎯 Tolerancia (5%): ${tolerance:.6f}")
            
            # Probar detección de señal
            signal = decide_grid_action(price, levels, None)
            
            if signal and signal.get('action'):
                print(f"   🚨 ¡SEÑAL DETECTADA!")
                print(f"   📈 Acción: {signal['action']}")
                print(f"   🎯 Nivel: ${signal['level']}")
            else:
                print(f"   ⏳ Sin señal (distancia > tolerancia)")
            
            print()
        
        # Probar con diferentes precios para ver la sensibilidad
        print("🧪 Pruebas de Sensibilidad:")
        print("-" * 30)
        
        # BTC - Probar con precio más cercano al nivel
        btc_test_price = 114400.0 + 50  # $50 más cerca del nivel
        btc_signal = decide_grid_action(btc_test_price, grid_configs['BTCUSDT']['levels'], None)
        print(f"BTC @ ${btc_test_price}: {'✅ Señal' if btc_signal.get('action') else '❌ Sin señal'}")
        
        # ETH - Probar con precio más cercano al nivel
        eth_test_price = 3556.0 + 2  # $2 más cerca del nivel
        eth_signal = decide_grid_action(eth_test_price, grid_configs['ETHUSDT']['levels'], None)
        print(f"ETH @ ${eth_test_price}: {'✅ Señal' if eth_signal.get('action') else '❌ Sin señal'}")
        
        # SPK - Probar con precio más cercano al nivel
        spk_test_price = 0.12071429 + 0.0005  # Más cerca del nivel
        spk_signal = decide_grid_action(spk_test_price, grid_configs['SPKUSDT']['levels'], None)
        print(f"SPK @ ${spk_test_price}: {'✅ Señal' if spk_signal.get('action') else '❌ Sin señal'}")
        
        print()
        print("✅ Pruebas completadas")
        
    except Exception as e:
        print(f"❌ Error en pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_grid_signals() 