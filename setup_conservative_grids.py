#!/usr/bin/env python3
"""
Script para configurar grids conservadores automáticamente
"""

import json
import requests
import time

def get_current_price(symbol):
    """Obtiene el precio actual de un símbolo"""
    try:
        response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
        price_data = response.json()
        return float(price_data['price'])
    except Exception as e:
        print(f"❌ Error obteniendo precio de {symbol}: {e}")
        return None

def calculate_grid_levels(current_price, grids=8):
    """Calcula niveles de grid conservadores"""
    # Rango conservador: ±5% del precio actual
    min_price = current_price * 0.95
    max_price = current_price * 1.05
    
    return min_price, max_price

def setup_grid_config(symbol, quantity, base_url, api_key):
    """Configura un grid para un símbolo específico"""
    
    print(f"\n🔧 Configurando grid para {symbol}...")
    
    # Obtener precio actual
    current_price = get_current_price(symbol)
    if not current_price:
        print(f"   ❌ No se pudo obtener precio para {symbol}")
        return False
    
    print(f"   📊 Precio actual: ${current_price:.2f}")
    
    # Calcular niveles de grid
    min_price, max_price = calculate_grid_levels(current_price)
    print(f"   📈 Rango de precios: ${min_price:.2f} - ${max_price:.2f}")
    
    # Configurar grid
    grid_config = {
        "symbol": symbol,
        "min_price": round(min_price, 2),
        "max_price": round(max_price, 2),
        "grids": 8,
        "quantity": quantity
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/trade/grid_config",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=grid_config
        )
        
        if response.status_code == 200:
            print(f"   ✅ Grid configurado exitosamente")
            print(f"      💰 Cantidad: {quantity}")
            print(f"      🔗 Grids: 8")
            return True
        else:
            print(f"   ❌ Error configurando grid: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error en la solicitud: {e}")
        return False

def main():
    """Función principal"""
    
    # Configuración
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🎯 Configurando Grids Conservadores Automáticamente")
    print("=" * 50)
    
    # Cargar configuración del análisis anterior
    try:
        with open('conservative_grid_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ No se encontró el archivo 'conservative_grid_config.json'")
        print("   Ejecuta primero 'analyze_trading_pairs.py'")
        return
    
    allocation = config['allocation']
    
    print(f"📋 Configurando {len(allocation)} grids...")
    print(f"💰 Inversión total: ${config['total_investment_ars']:,.2f} ARS")
    
    # Configurar cada grid
    successful_configs = []
    
    for item in allocation:
        symbol = item['symbol']
        quantity = item['quantity']
        
        success = setup_grid_config(symbol, quantity, base_url, api_key)
        if success:
            successful_configs.append(item)
        
        # Pausa entre configuraciones
        time.sleep(1)
    
    # Resumen
    print(f"\n🎉 Resumen de configuración:")
    print(f"   ✅ Grids configurados: {len(successful_configs)}/{len(allocation)}")
    
    if successful_configs:
        print(f"\n📊 Grids activos:")
        for item in successful_configs:
            print(f"   • {item['symbol']}: {item['quantity']:.6f} {item['baseAsset']}")
        
        # Crear archivo de configuración final
        final_config = {
            'active_grids': successful_configs,
            'total_investment_ars': sum(item['investmentARS'] for item in successful_configs),
            'setup_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('active_grids_config.json', 'w') as f:
            json.dump(final_config, f, indent=2)
        
        print(f"\n💾 Configuración guardada en 'active_grids_config.json'")
        
        # Enviar alerta de Telegram
        alert_message = f"🎯 Grids Conservadores Configurados\n\n"
        alert_message += f"📊 Grids activos: {len(successful_configs)}\n"
        alert_message += f"💰 Inversión total: ${final_config['total_investment_ars']:,.2f} ARS\n\n"
        
        for item in successful_configs:
            alert_message += f"• {item['symbol']}: {item['quantity']:.6f} {item['baseAsset']}\n"
        
        # Enviar alerta
        try:
            telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
            telegram_data = {
                "chat_id": "1248403886",
                "text": alert_message
            }
            requests.post(telegram_url, data=telegram_data)
            print(f"\n📱 Alerta enviada a Telegram")
        except Exception as e:
            print(f"\n❌ Error enviando alerta: {e}")

if __name__ == "__main__":
    main() 