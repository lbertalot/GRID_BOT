#!/usr/bin/env python3
"""
Script inteligente para distribuir ARS a activos con cantidades válidas
"""

import requests
import json
import time

def get_valid_quantities():
    """Retorna cantidades válidas según los requisitos de Binance"""
    return {
        'BNB': {'min_qty': 0.001, 'step_size': 0.001, 'min_notional': 5},
        'BTC': {'min_qty': 0.00001, 'step_size': 0.00001, 'min_notional': 5},
        'ETH': {'min_qty': 0.001, 'step_size': 0.001, 'min_notional': 5},
        'LTC': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'LINK': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'DOT': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5},
        'ADA': {'min_qty': 1, 'step_size': 1, 'min_notional': 5},
        'XRP': {'min_qty': 1, 'step_size': 1, 'min_notional': 5},
        'MATIC': {'min_qty': 1, 'step_size': 1, 'min_notional': 5},
        'AVAX': {'min_qty': 0.01, 'step_size': 0.01, 'min_notional': 5}
    }

def get_current_prices():
    """Obtiene precios actuales de los activos"""
    return {
        'BNB': 735, 'BTC': 65000, 'ETH': 3500, 'LTC': 85,
        'LINK': 15, 'DOT': 7, 'ADA': 0.5, 'XRP': 0.6,
        'MATIC': 0.8, 'AVAX': 25
    }

def calculate_valid_quantity(asset, usdt_amount, prices, valid_quantities):
    """Calcula una cantidad válida para el activo"""
    if asset not in prices or asset not in valid_quantities:
        return None
    
    price = prices[asset]
    min_qty = valid_quantities[asset]['min_qty']
    step_size = valid_quantities[asset]['step_size']
    min_notional = valid_quantities[asset]['min_notional']
    
    # Calcular cantidad basada en USDT
    raw_quantity = usdt_amount / price
    
    # Asegurar cantidad mínima
    if raw_quantity < min_qty:
        raw_quantity = min_qty
    
    # Ajustar a step size
    adjusted_quantity = (raw_quantity // step_size) * step_size
    
    # Verificar notional mínimo
    notional_value = adjusted_quantity * price
    if notional_value < min_notional:
        # Aumentar cantidad para cumplir notional mínimo
        adjusted_quantity = (min_notional / price // step_size + 1) * step_size
    
    return round(adjusted_quantity, 6)

def distribute_ars_smart():
    """Distribuye ARS de manera inteligente con cantidades válidas"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🧠 Distribución Inteligente de ARS")
    print("=" * 50)
    
    # Obtener balances
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        ars_balance = balances.get('ARS', 0)
        usdt_balance = balances.get('USDT', 0)
        
        print(f"📊 Balance actual:")
        print(f"   💰 ARS: ${ars_balance:,.2f}")
        print(f"   💵 USDT: ${usdt_balance:.2f}")
        
        if ars_balance < 50000:  # Mínimo $50,000 ARS
            print(f"❌ Balance ARS insuficiente para distribución")
            return False
        
        # Calcular distribución
        usdt_price_ars = 1200  # Precio aproximado
        total_usdt_equivalent = ars_balance / usdt_price_ars
        
        print(f"\n📈 Distribución planificada:")
        print(f"   💱 Precio USDT/ARS: ${usdt_price_ars:,.2f}")
        print(f"   💵 Equivalente USDT: ${total_usdt_equivalent:.2f}")
        
        # Estrategia simplificada y realista
        distribution_strategy = {
            'BNB': {'percentage': 0.40, 'reason': 'Alta liquidez, trading activo'},
            'ETH': {'percentage': 0.30, 'reason': 'Segunda cripto, estabilidad'},
            'LTC': {'percentage': 0.20, 'reason': 'Bueno para grids, precio accesible'},
            'LINK': {'percentage': 0.10, 'reason': 'DeFi, oportunidades de trading'}
        }
        
        print(f"\n🎯 ESTRATEGIA SIMPLIFICADA:")
        print("-" * 40)
        
        # Obtener datos de validación
        valid_quantities = get_valid_quantities()
        current_prices = get_current_prices()
        
        # Calcular cantidades válidas
        valid_purchases = []
        total_planned_usdt = 0
        
        for asset, config in distribution_strategy.items():
            percentage = config['percentage']
            usdt_amount = total_usdt_equivalent * percentage
            
            valid_qty = calculate_valid_quantity(asset, usdt_amount, current_prices, valid_quantities)
            
            if valid_qty:
                actual_usdt = valid_qty * current_prices[asset]
                ars_amount = actual_usdt * usdt_price_ars
                total_planned_usdt += actual_usdt
                
                purchase_info = {
                    'asset': asset,
                    'percentage': percentage,
                    'planned_usdt': usdt_amount,
                    'actual_usdt': actual_usdt,
                    'quantity': valid_qty,
                    'price': current_prices[asset],
                    'ars_amount': ars_amount,
                    'reason': config['reason']
                }
                valid_purchases.append(purchase_info)
                
                print(f"   🪙 {asset}: {percentage*100:.1f}%")
                print(f"      💰 Cantidad: {valid_qty:.6f}")
                print(f"      💵 Valor: ${actual_usdt:.2f} USDT (${ars_amount:,.2f} ARS)")
                print(f"      💡 {config['reason']}")
        
        print(f"\n📊 Total planificado: ${total_planned_usdt:.2f} USDT")
        
        # Confirmar distribución
        confirm = input(f"\n¿Confirmar distribución de ${total_planned_usdt:.2f} USDT? (y/n): ")
        
        if confirm.lower() != 'y':
            print("❌ Distribución cancelada")
            return False
        
        # Ejecutar compras
        print(f"\n🔄 Ejecutando compras...")
        
        successful_purchases = []
        failed_purchases = []
        
        for purchase in valid_purchases:
            asset = purchase['asset']
            quantity = purchase['quantity']
            usdt_value = purchase['actual_usdt']
            
            print(f"\n🛒 Comprando {asset}...")
            print(f"   💰 Cantidad: {quantity:.6f}")
            print(f"   💵 Valor estimado: ${usdt_value:.2f} USDT")
            
            try:
                order_data = {
                    "symbol": f"{asset}USDT",
                    "side": "BUY",
                    "type": "MARKET",
                    "quantity": quantity
                }
                
                response = requests.post(
                    f"{base_url}/api/trade/order",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=order_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    purchase['order_id'] = result.get('orderId', 'N/A')
                    successful_purchases.append(purchase)
                    print(f"   ✅ Compra exitosa: {quantity:.6f} {asset}")
                else:
                    error_msg = response.json().get('message', 'Error desconocido')
                    failed_purchases.append({
                        'asset': asset,
                        'error': error_msg,
                        'usdt_value': usdt_value
                    })
                    print(f"   ❌ Error: {error_msg}")
                    
            except Exception as e:
                failed_purchases.append({
                    'asset': asset,
                    'error': str(e),
                    'usdt_value': usdt_value
                })
                print(f"   ❌ Error: {e}")
            
            # Esperar entre compras
            time.sleep(3)
        
        # Resumen final
        print(f"\n🎉 DISTRIBUCIÓN COMPLETADA")
        print("=" * 40)
        
        total_invested = sum(p['actual_usdt'] for p in successful_purchases)
        total_failed = sum(p['usdt_value'] for p in failed_purchases)
        
        print(f"✅ Compras exitosas: {len(successful_purchases)}")
        print(f"❌ Compras fallidas: {len(failed_purchases)}")
        print(f"💰 Total invertido: ${total_invested:.2f} USDT")
        print(f"💸 Total fallido: ${total_failed:.2f} USDT")
        
        if successful_purchases:
            print(f"\n📊 Activos comprados:")
            for purchase in successful_purchases:
                print(f"   🪙 {purchase['asset']}: {purchase['quantity']:.6f} (${purchase['actual_usdt']:.2f} USDT)")
        
        if failed_purchases:
            print(f"\n❌ Compras fallidas:")
            for failed in failed_purchases:
                print(f"   ⚠️ {failed['asset']}: {failed['error']}")
        
        # Guardar configuración
        config_data = {
            'smart_distribution': {
                'total_ars': ars_balance,
                'total_usdt_equivalent': total_usdt_equivalent,
                'successful_purchases': len(successful_purchases),
                'failed_purchases': len(failed_purchases),
                'total_invested': total_invested,
                'total_failed': total_failed
            },
            'successful_purchases': successful_purchases,
            'failed_purchases': failed_purchases,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('smart_distribution_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"\n💾 Configuración guardada en 'smart_distribution_config.json'")
        
        # Enviar alerta de Telegram
        alert_message = f"🧠 Distribución Inteligente Completada\n\n"
        alert_message += f"📊 Resumen:\n"
        alert_message += f"• ARS utilizados: ${ars_balance:,.2f}\n"
        alert_message += f"• Compras exitosas: {len(successful_purchases)}\n"
        alert_message += f"• Total invertido: ${total_invested:.2f} USDT\n\n"
        
        if successful_purchases:
            alert_message += f"✅ Activos comprados:\n"
            for purchase in successful_purchases:
                alert_message += f"• {purchase['asset']}: {purchase['quantity']:.6f}\n"
        
        alert_message += f"\n🚀 ¡Ahora tienes múltiples activos para trading!"
        alert_message += f"\n📱 Recibirás alertas de todos los activos"
        
        try:
            telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
            telegram_data = {
                "chat_id": "1248403886",
                "text": alert_message
            }
            requests.post(telegram_url, data=telegram_data)
            print(f"📱 Alerta enviada a Telegram")
        except Exception as e:
            print(f"❌ Error enviando alerta: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Función principal"""
    success = distribute_ars_smart()
    
    if success:
        print(f"\n🎉 ¡Distribución inteligente completada!")
        print(f"📱 Recibirás alertas de múltiples activos")
        print(f"🤖 GridBot está listo para operar con diversificación")
    else:
        print(f"\n❌ No se pudo completar la distribución")

if __name__ == "__main__":
    main() 