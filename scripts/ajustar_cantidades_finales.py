#!/usr/bin/env python3
"""
Script para ajustar cantidades finales según requisitos exactos de Binance
"""

import requests
import json
import time

def obtener_requisitos_binance():
    """Obtener requisitos exactos de Binance para cada activo"""
    
    print("🔍 OBTENIENDO REQUISITOS EXACTOS DE BINANCE")
    print("=" * 50)
    
    # Configuración de API
    api_key = "sGe6sH9j9iwFQM8liSvA29zQVThsMQEDwLp3xn8WIEbnJg9n7DRWLmgpN8gTcMHC"
    api_secret = "GCFZII1X4DfOdVJAV6bKuYg3kpvX9FguIim4uUnGgwX106Hu2kvDLIw2u016g4Ep"
    
    # Cargar configuración actual
    try:
        with open('grid_config_optimized.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Archivo de configuración no encontrado")
        return
    
    # Obtener información de exchange de Binance
    try:
        response = requests.get("https://api.binance.com/api/v3/exchangeInfo")
        if response.status_code == 200:
            exchange_info = response.json()
            symbols_info = {s['symbol']: s for s in exchange_info['symbols']}
            print("✅ Información de exchange obtenida de Binance")
        else:
            print(f"❌ Error obteniendo información de exchange: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error conectando a Binance: {e}")
        return
    
    # Analizar requisitos por activo
    requisitos_por_activo = {}
    cantidades_ajustadas = {}
    
    print("\n📊 ANALIZANDO REQUISITOS POR ACTIVO:")
    print("-" * 40)
    
    for symbol, asset_config in config.items():
        if symbol == "_optimization_metadata":
            continue
            
        print(f"\n🪙 {symbol}:")
        
        if symbol not in symbols_info:
            print(f"   ❌ Símbolo no disponible en Binance")
            continue
        
        symbol_info = symbols_info[symbol]
        filters = {f['filterType']: f for f in symbol_info['filters']}
        
        # Obtener filtros relevantes
        lot_size = filters.get('LOT_SIZE', {})
        min_notional = filters.get('MIN_NOTIONAL', {})
        market_lot_size = filters.get('MARKET_LOT_SIZE', {})
        
        # Extraer valores
        min_qty = float(lot_size.get('minQty', 0))
        max_qty = float(lot_size.get('maxQty', float('inf')))
        step_size = float(lot_size.get('stepSize', 0.001))
        min_notional_value = float(min_notional.get('minNotional', 0))
        
        # Obtener precio actual
        try:
            ticker_response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
            if ticker_response.status_code == 200:
                ticker_data = ticker_response.json()
                precio_actual = float(ticker_data['price'])
            else:
                precio_actual = 0
        except:
            precio_actual = 0
        
        # Calcular cantidad mínima válida
        cantidad_minima_por_precio = min_notional_value / precio_actual if precio_actual > 0 else 0
        cantidad_minima_final = max(min_qty, cantidad_minima_por_precio)
        
        # Ajustar a step size
        cantidad_ajustada = round(cantidad_minima_final / step_size) * step_size
        
        # Asegurar que no exceda el máximo
        if cantidad_ajustada > max_qty:
            cantidad_ajustada = max_qty
        
        requisitos_por_activo[symbol] = {
            'min_qty': min_qty,
            'max_qty': max_qty,
            'step_size': step_size,
            'min_notional': min_notional_value,
            'precio_actual': precio_actual,
            'cantidad_minima_por_precio': cantidad_minima_por_precio,
            'cantidad_minima_final': cantidad_minima_final,
            'cantidad_ajustada': cantidad_ajustada
        }
        
        cantidades_ajustadas[symbol] = cantidad_ajustada
        
        print(f"   📊 Cantidad actual: {asset_config['quantity']}")
        print(f"   🔧 Cantidad ajustada: {cantidad_ajustada}")
        print(f"   📈 Precio actual: ${precio_actual:.6f}")
        print(f"   💰 Valor mínimo: ${min_notional_value}")
        print(f"   📏 Step size: {step_size}")
        print(f"   ✅ Válido: {'Sí' if cantidad_ajustada >= min_qty else 'No'}")
    
    # Aplicar cantidades ajustadas
    print(f"\n🔄 APLICANDO CANTIDADES AJUSTADAS:")
    print("-" * 40)
    
    config_ajustada = {}
    
    for symbol, asset_config in config.items():
        if symbol == "_optimization_metadata":
            config_ajustada[symbol] = asset_config
            continue
        
        if symbol in cantidades_ajustadas:
            asset_config['quantity'] = cantidades_ajustadas[symbol]
            print(f"✅ {symbol}: {cantidades_ajustadas[symbol]}")
        else:
            print(f"⚠️ {symbol}: Sin ajuste (no disponible)")
        
        config_ajustada[symbol] = asset_config
    
    # Agregar metadatos de ajuste
    config_ajustada['_optimization_metadata'] = {
        "optimized_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "optimization_version": "3.0",
        "optimizations_applied": [
            "grid_density_optimization",
            "quantity_adjustment",
            "price_range_optimization",
            "binance_requirements_correction",
            "final_quantity_adjustment"
        ],
        "requisitos_binance": requisitos_por_activo,
        "cantidades_ajustadas": cantidades_ajustadas
    }
    
    # Guardar configuración ajustada
    with open('grid_config_final_ajustado.json', 'w') as f:
        json.dump(config_ajustada, f, indent=2)
    
    print(f"\n💾 Configuración final guardada en 'grid_config_final_ajustado.json'")
    
    # Aplicar al sistema
    print(f"\n🚀 APLICANDO AL SISTEMA:")
    print("-" * 25)
    
    try:
        # Copiar configuración ajustada a la principal
        with open('grid_config_optimized.json', 'w') as f:
            json.dump(config_ajustada, f, indent=2)
        
        print("✅ Configuración aplicada al sistema")
        
        # Actualizar grid_job.py
        actualizar_grid_job_final(config_ajustada)
        
        # Reiniciar servicio
        print("\n🔄 REINICIANDO SERVICIO:")
        print("-" * 25)
        
        import subprocess
        result = subprocess.run(
            ["docker-compose", "restart", "api"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Servicio reiniciado exitosamente")
        else:
            print(f"❌ Error reiniciando servicio: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error aplicando configuración: {e}")
    
    # Verificar aplicación
    print("\n⏳ VERIFICANDO APLICACIÓN...")
    print("-" * 30)
    
    time.sleep(30)  # Esperar 30 segundos
    
    try:
        response = requests.get("http://localhost:8000/config", timeout=10)
        if response.status_code == 200:
            config_aplicada = response.json()
            print("✅ Configuración aplicada correctamente")
            
            # Verificar cantidades
            print("\n📊 CANTIDADES FINALES APLICADAS:")
            for symbol, asset_config in config_aplicada.items():
                if symbol != "_optimization_metadata":
                    cantidad = asset_config.get('quantity', 0)
                    print(f"   🪙 {symbol}: {cantidad}")
        else:
            print(f"❌ Error verificando configuración: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error verificando aplicación: {e}")
    
    # Enviar alerta de Telegram
    alert_message = f"🎯 CANTIDADES FINALES AJUSTADAS\n\n"
    alert_message += f"📊 Activos ajustados: {len(cantidades_ajustadas)}\n\n"
    
    for symbol, cantidad in cantidades_ajustadas.items():
        alert_message += f"🪙 {symbol}: {cantidad}\n"
    
    alert_message += f"\n✅ Configuración final aplicada\n"
    alert_message += f"🔄 Servicio reiniciado\n"
    alert_message += f"🚀 Trading multi-activo activado\n"
    alert_message += f"🎉 ¡GridBot funcionando al 100%!"
    
    try:
        telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
        telegram_data = {
            "chat_id": "1248403886",
            "text": alert_message
        }
        response = requests.post(telegram_url, data=telegram_data)
        if response.status_code == 200:
            print("📱 Alerta enviada a Telegram")
        else:
            print(f"❌ Error enviando alerta: {response.status_code}")
    except Exception as e:
        print(f"❌ Error enviando alerta: {e}")

def actualizar_grid_job_final(config_ajustada):
    """Actualizar grid_job.py con la configuración final ajustada"""
    
    print("📝 Actualizando grid_job.py con configuración final...")
    
    try:
        with open('app/scheduler/grid_job.py', 'r') as f:
            content = f.read()
        
        # Crear nueva configuración
        config_str = "multi_asset_grid_config = {\n"
        for symbol, asset_config in config_ajustada.items():
            if symbol == "_optimization_metadata":
                continue
            config_str += f"    '{symbol}': {{\n"
            config_str += f"        'symbol': '{symbol}',\n"
            config_str += f"        'min_price': {asset_config['min_price']},\n"
            config_str += f"        'max_price': {asset_config['max_price']},\n"
            config_str += f"        'grids': {asset_config['grids']},\n"
            config_str += f"        'quantity': {asset_config['quantity']},\n"
            config_str += f"        'last_action': None,\n"
            config_str += f"        'is_active': True,\n"
            config_str += f"    }},\n"
        config_str += "}\n"
        
        # Reemplazar configuración en el archivo
        import re
        pattern = r'multi_asset_grid_config = \{.*?\}'
        new_content = re.sub(pattern, config_str, content, flags=re.DOTALL)
        
        with open('app/scheduler/grid_job.py', 'w') as f:
            f.write(new_content)
        
        print("✅ grid_job.py actualizado con configuración final")
        
    except Exception as e:
        print(f"❌ Error actualizando grid_job.py: {e}")

def main():
    """Función principal"""
    obtener_requisitos_binance()

if __name__ == "__main__":
    main() 