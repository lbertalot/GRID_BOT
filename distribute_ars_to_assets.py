#!/usr/bin/env python3
"""
Script para distribuir ARS a múltiples activos para maximizar trading
"""

import requests
import json
import time

def get_usdt_price():
    """Obtiene el precio actual de USDT en ARS"""
    try:
        # Usar precio aproximado de USDT en ARS
        # En producción se obtendría de una API de precios
        return 1200  # Precio aproximado USDT/ARS
    except:
        return 1200

def distribute_ars_to_assets():
    """Distribuye ARS a múltiples activos para trading"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("💰 Distribuyendo ARS a Activos para Trading")
    print("=" * 55)
    
    # Obtener balances
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        ars_balance = balances.get('ARS', 0)
        usdt_balance = balances.get('USDT', 0)
        
        print(f"📊 Balance actual:")
        print(f"   💰 ARS: ${ars_balance:,.2f}")
        print(f"   💵 USDT: ${usdt_balance:.2f}")
        
        if ars_balance < 10000:
            print(f"❌ Balance ARS insuficiente para distribución")
            return False
        
        # Calcular distribución
        usdt_price_ars = get_usdt_price()
        total_usdt_equivalent = ars_balance / usdt_price_ars
        
        print(f"\n📈 Distribución planificada:")
        print(f"   💱 Precio USDT/ARS: ${usdt_price_ars:,.2f}")
        print(f"   💵 Equivalente USDT: ${total_usdt_equivalent:.2f}")
        
        # Estrategia de distribución
        distribution_strategy = {
            'major_assets': {
                'BNB': {'percentage': 0.25, 'reason': 'Alta liquidez, trading activo'},
                'BTC': {'percentage': 0.20, 'reason': 'Activo principal, estabilidad'},
                'ETH': {'percentage': 0.20, 'reason': 'Segunda cripto, buena volatilidad'},
                'LTC': {'percentage': 0.15, 'reason': 'Bueno para grids, precio accesible'},
                'LINK': {'percentage': 0.10, 'reason': 'DeFi, oportunidades de trading'},
                'DOT': {'percentage': 0.10, 'reason': 'Polkadot, crecimiento potencial'}
            },
            'altcoins': {
                'ADA': {'percentage': 0.05, 'reason': 'Cardano, comunidad fuerte'},
                'XRP': {'percentage': 0.05, 'reason': 'Ripple, volumen alto'},
                'MATIC': {'percentage': 0.05, 'reason': 'Polygon, DeFi activo'},
                'AVAX': {'percentage': 0.05, 'reason': 'Avalanche, ecosistema creciente'}
            }
        }
        
        print(f"\n🎯 ESTRATEGIA DE DISTRIBUCIÓN:")
        print("-" * 40)
        
        # Mostrar distribución planificada
        total_percentage = 0
        for category, assets in distribution_strategy.items():
            print(f"\n📊 {category.upper()}:")
            for asset, config in assets.items():
                percentage = config['percentage']
                usdt_amount = total_usdt_equivalent * percentage
                ars_amount = usdt_amount * usdt_price_ars
                total_percentage += percentage
                
                print(f"   🪙 {asset}: {percentage*100:.1f}% = ${usdt_amount:.2f} USDT (${ars_amount:,.2f} ARS)")
                print(f"      💡 {config['reason']}")
        
        print(f"\n📊 Total: {total_percentage*100:.1f}% de distribución")
        
        # Confirmar distribución
        confirm = input(f"\n¿Confirmar distribución de ${ars_balance:,.2f} ARS? (y/n): ")
        
        if confirm.lower() != 'y':
            print("❌ Distribución cancelada")
            return False
        
        # Ejecutar compras
        print(f"\n🔄 Ejecutando compras...")
        
        successful_purchases = []
        failed_purchases = []
        
        for category, assets in distribution_strategy.items():
            for asset, config in assets.items():
                percentage = config['percentage']
                usdt_amount = total_usdt_equivalent * percentage
                
                # Calcular cantidad aproximada (usar precio estimado)
                estimated_prices = {
                    'BNB': 735, 'BTC': 65000, 'ETH': 3500, 'LTC': 85,
                    'LINK': 15, 'DOT': 7, 'ADA': 0.5, 'XRP': 0.6,
                    'MATIC': 0.8, 'AVAX': 25
                }
                
                estimated_price = estimated_prices.get(asset, 1)
                estimated_quantity = usdt_amount / estimated_price
                
                print(f"\n🛒 Comprando {asset}...")
                print(f"   💰 Cantidad estimada: {estimated_quantity:.6f}")
                print(f"   💵 Valor estimado: ${usdt_amount:.2f} USDT")
                
                try:
                    # Intentar compra
                    order_data = {
                        "symbol": f"{asset}USDT",
                        "side": "BUY",
                        "type": "MARKET",
                        "quantity": round(estimated_quantity, 6)
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
                        purchase_info = {
                            'asset': asset,
                            'quantity': estimated_quantity,
                            'usdt_value': usdt_amount,
                            'order_id': result.get('orderId', 'N/A'),
                            'category': category
                        }
                        successful_purchases.append(purchase_info)
                        print(f"   ✅ Compra exitosa: {estimated_quantity:.6f} {asset}")
                    else:
                        error_msg = response.json().get('message', 'Error desconocido')
                        failed_purchases.append({
                            'asset': asset,
                            'error': error_msg,
                            'usdt_value': usdt_amount
                        })
                        print(f"   ❌ Error: {error_msg}")
                        
                except Exception as e:
                    failed_purchases.append({
                        'asset': asset,
                        'error': str(e),
                        'usdt_value': usdt_amount
                    })
                    print(f"   ❌ Error: {e}")
                
                # Esperar entre compras
                time.sleep(2)
        
        # Resumen final
        print(f"\n🎉 DISTRIBUCIÓN COMPLETADA")
        print("=" * 40)
        
        total_invested = sum(p['usdt_value'] for p in successful_purchases)
        total_failed = sum(p['usdt_value'] for p in failed_purchases)
        
        print(f"✅ Compras exitosas: {len(successful_purchases)}")
        print(f"❌ Compras fallidas: {len(failed_purchases)}")
        print(f"💰 Total invertido: ${total_invested:.2f} USDT")
        print(f"💸 Total fallido: ${total_failed:.2f} USDT")
        
        if successful_purchases:
            print(f"\n📊 Activos comprados:")
            for purchase in successful_purchases:
                print(f"   🪙 {purchase['asset']}: {purchase['quantity']:.6f} (${purchase['usdt_value']:.2f} USDT)")
        
        if failed_purchases:
            print(f"\n❌ Compras fallidas:")
            for failed in failed_purchases:
                print(f"   ⚠️ {failed['asset']}: {failed['error']}")
        
        # Guardar configuración
        config_data = {
            'distribution_summary': {
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
        
        with open('ars_distribution_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"\n💾 Configuración guardada en 'ars_distribution_config.json'")
        
        # Enviar alerta de Telegram
        alert_message = f"💰 Distribución de ARS Completada\n\n"
        alert_message += f"📊 Resumen:\n"
        alert_message += f"• ARS distribuidos: ${ars_balance:,.2f}\n"
        alert_message += f"• Equivalente USDT: ${total_usdt_equivalent:.2f}\n"
        alert_message += f"• Compras exitosas: {len(successful_purchases)}\n"
        alert_message += f"• Compras fallidas: {len(failed_purchases)}\n"
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
    success = distribute_ars_to_assets()
    
    if success:
        print(f"\n🎉 ¡Distribución completada exitosamente!")
        print(f"📱 Recibirás alertas de múltiples activos")
        print(f"🤖 GridBot está listo para operar con diversificación")
    else:
        print(f"\n❌ No se pudo completar la distribución")

if __name__ == "__main__":
    main() 