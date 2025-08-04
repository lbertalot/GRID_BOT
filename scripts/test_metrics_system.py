#!/usr/bin/env python3
"""
Script para probar el nuevo sistema de métricas centralizado
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

async def test_metrics_system():
    """Prueba el sistema de métricas centralizado"""
    try:
        print("🧪 Probando Sistema de Métricas Centralizado")
        print("=" * 50)
        
        from app.core.metrics_manager import metrics_manager
        
        print("1️⃣ Inicializando métricas...")
        # Las métricas ya están inicializadas en el constructor
        
        print("2️⃣ Actualizando todas las métricas...")
        await metrics_manager.update_all_metrics()
        
        print("3️⃣ Registrando algunos trades de prueba...")
        # Simular algunos trades
        test_trades = [
            ("BTCUSDT", "BUY", 0.001, 114500.0),
            ("ETHUSDT", "SELL", 0.01, 3550.0),
            ("SPKUSDT", "BUY", 100.0, 0.12),
            ("BTCUSDT", "SELL", 0.0005, 115000.0),
        ]
        
        for symbol, side, quantity, price in test_trades:
            metrics_manager.record_trade_execution(symbol, side, quantity, price, 0.5)
            print(f"   📊 Trade registrado: {side} {quantity} {symbol} @ ${price}")
        
        print("4️⃣ Registrando señales detectadas...")
        test_signals = [
            ("BTCUSDT", "BUY"),
            ("ETHUSDT", "SELL"),
            ("SPKUSDT", "BUY"),
        ]
        
        for symbol, action in test_signals:
            metrics_manager.record_signal_detected(symbol, action)
            print(f"   📡 Señal registrada: {action} {symbol}")
        
        print("5️⃣ Registrando algunos errores...")
        test_errors = [
            ("api_timeout", "binance"),
            ("insufficient_balance", "grid_manager"),
            ("invalid_order", "binance"),
        ]
        
        for error_type, service in test_errors:
            metrics_manager.record_error(error_type, service)
            print(f"   ❌ Error registrado: {error_type} en {service}")
        
        print("6️⃣ Actualizando métricas finales...")
        await metrics_manager.update_all_metrics()
        
        print("7️⃣ Verificando métricas en el endpoint...")
        import requests
        try:
            response = requests.get("http://localhost:8000/metrics", timeout=10)
            if response.status_code == 200:
                metrics_content = response.text
                
                # Verificar métricas específicas
                metrics_to_check = [
                    "trading_active",
                    "trades_total",
                    "profit_total_usdt",
                    "portfolio_total_value_usdt",
                    "signals_detected",
                    "errors_total"
                ]
                
                print("   📊 Métricas encontradas:")
                for metric in metrics_to_check:
                    if metric in metrics_content:
                        print(f"      ✅ {metric}")
                    else:
                        print(f"      ❌ {metric} (no encontrada)")
                
                # Mostrar algunas métricas específicas
                lines = metrics_content.split('\n')
                for line in lines:
                    if any(metric in line for metric in metrics_to_check):
                        if not line.startswith('#'):
                            print(f"      📈 {line}")
                
            else:
                print(f"   ❌ Error obteniendo métricas: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error conectando al endpoint: {e}")
        
        print()
        print("✅ Pruebas del sistema de métricas completadas")
        print("💡 Las métricas ahora deberían aparecer en Grafana")
        
    except Exception as e:
        print(f"❌ Error en pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_metrics_system()) 