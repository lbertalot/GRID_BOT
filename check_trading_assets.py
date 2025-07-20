#!/usr/bin/env python3
"""
Script para verificar qué activos son mejores para trading
"""

import requests
import json

def check_trading_assets():
    """Verifica qué activos son mejores para trading"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🔍 Analizando Activos para Trading")
    print("=" * 50)
    
    # Obtener balances
    try:
        response = requests.get(f"{base_url}/api/trade/balances", headers={"Authorization": f"Bearer {api_key}"})
        balances = response.json()
        
        # Filtrar activos con balance > 0
        assets_with_balance = {k: v for k, v in balances.items() if v > 0}
        
        print(f"📊 Activos disponibles: {len(assets_with_balance)}")
        print()
        
        # Categorizar activos
        major_assets = ['USDT', 'BNB', 'BTC', 'ETH', 'LTC', 'LINK', 'DOT', 'ADA', 'XRP']
        stable_coins = ['USDT', 'USDC', 'BUSD', 'DAI']
        
        print("🏆 ACTIVOS PRINCIPALES (Mejor liquidez):")
        print("-" * 40)
        
        for asset in major_assets:
            if asset in assets_with_balance:
                balance = assets_with_balance[asset]
                if asset == 'USDT':
                    print(f"   💰 {asset}: {balance:.2f} (Estable)")
                else:
                    print(f"   🪙 {asset}: {balance:.6f}")
        
        print()
        print("📈 TOKENS CON CANTIDADES SIGNIFICATIVAS:")
        print("-" * 40)
        
        # Ordenar por cantidad (excluyendo USDT y ARS)
        significant_tokens = []
        for asset, balance in assets_with_balance.items():
            if asset not in ['USDT', 'ARS'] and balance > 0.01:
                significant_tokens.append((asset, balance))
        
        # Ordenar por cantidad descendente
        significant_tokens.sort(key=lambda x: x[1], reverse=True)
        
        for asset, balance in significant_tokens[:10]:  # Top 10
            print(f"   🎯 {asset}: {balance:.6f}")
        
        print()
        print("💡 RECOMENDACIONES PARA TRADING:")
        print("-" * 40)
        
        # Analizar mejores opciones
        recommendations = []
        
        # 1. Verificar si BNB es suficiente
        bnb_balance = assets_with_balance.get('BNB', 0)
        if bnb_balance >= 0.005:
            recommendations.append(f"✅ BNB ({bnb_balance:.6f}) - Suficiente para trading")
        else:
            recommendations.append(f"⚠️ BNB ({bnb_balance:.6f}) - Muy bajo, considerar comprar")
        
        # 2. Verificar otros activos principales
        for asset in ['BTC', 'ETH', 'LTC', 'LINK', 'DOT']:
            if asset in assets_with_balance:
                balance = assets_with_balance[asset]
                if balance > 0.001:  # Cantidad mínima para trading
                    recommendations.append(f"✅ {asset} ({balance:.6f}) - Bueno para trading")
        
        # 3. Verificar tokens con cantidades significativas
        for asset, balance in significant_tokens[:3]:
            if balance > 0.05:  # Cantidad alta
                recommendations.append(f"🎯 {asset} ({balance:.6f}) - Cantidad alta, buen candidato")
        
        for rec in recommendations:
            print(f"   {rec}")
        
        print()
        print("🚀 ACCIONES RECOMENDADAS:")
        print("-" * 40)
        
        # Determinar mejor acción
        if bnb_balance >= 0.005:
            print("   1. ✅ Usar BNB actual para trading")
            print("   2. 🔧 Ajustar configuración del grid a 0.004 BNB")
            print("   3. 🎯 Comenzar operaciones inmediatamente")
        elif bnb_balance > 0.002:
            print("   1. 🛒 Comprar más BNB (recomendado)")
            print("   2. 🔧 O ajustar grid a 0.002 BNB")
            print("   3. ⚠️ Cantidad mínima para operar")
        else:
            print("   1. 🛒 Comprar BNB para trading")
            print("   2. 💰 Usar USDT disponible")
            print("   3. 🎯 Configurar grid automáticamente")
        
        # Verificar si hay otros activos buenos
        good_assets = []
        for asset, balance in significant_tokens:
            if balance > 0.05 and asset not in ['BNB', 'USDT']:
                good_assets.append(asset)
        
        if good_assets:
            print(f"   4. 🎯 Considerar trading con: {', '.join(good_assets[:3])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Función principal"""
    check_trading_assets()

if __name__ == "__main__":
    main() 