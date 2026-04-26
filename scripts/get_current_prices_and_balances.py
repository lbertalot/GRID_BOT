#!/usr/bin/env python3
"""
Script para obtener precios actuales y saldos de Binance
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.binance_async import AsyncBinanceWrapper


async def get_current_data():
    """Obtiene precios actuales y saldos"""
    try:
        print("🚀 Obteniendo datos actuales de Binance...")

        binance = AsyncBinanceWrapper()

        # Símbolos a verificar
        symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "BNBUSDT",
            "SPKUSDT",
            "ADAUSDT",
            "DOTUSDT",
            "LINKUSDT",
            "MATICUSDT",
            "AVAXUSDT",
        ]

        # Obtener precios actuales
        print("📊 Obteniendo precios actuales...")
        prices = {}
        for symbol in symbols:
            try:
                price = await binance.get_price(symbol)
                prices[symbol] = price
                print(f"   {symbol}: ${price:.4f}")
            except Exception as e:
                print(f"   ⚠️ Error obteniendo precio de {symbol}: {e}")
                prices[symbol] = None

        # Obtener saldos
        print("\n💰 Obteniendo saldos...")
        balances = await asyncio.to_thread(binance.client.get_account)
        balances = {
            b["asset"]: float(b["free"])
            for b in balances["balances"]
            if float(b["free"]) > 0
        }

        # Filtrar solo los activos que nos interesan
        relevant_balances = {}
        for asset in [
            "BTC",
            "ETH",
            "BNB",
            "SPK",
            "ADA",
            "DOT",
            "LINK",
            "MATIC",
            "AVAX",
            "USDT",
        ]:
            if asset in balances and balances[asset] > 0:
                relevant_balances[asset] = balances[asset]
                print(f"   {asset}: {balances[asset]:.8f}")

        # Calcular valores en USDT
        print("\n💵 Valores en USDT:")
        total_value = 0
        for asset, balance in relevant_balances.items():
            if asset == "USDT":
                value = balance
            else:
                symbol = f"{asset}USDT"
                if symbol in prices and prices[symbol]:
                    value = balance * prices[symbol]
                else:
                    value = 0
            total_value += value
            print(f"   {asset}: ${value:.2f}")

        print(f"\n🏦 Valor total del portafolio: ${total_value:.2f}")

        # Guardar datos
        data = {
            "timestamp": datetime.now().isoformat(),
            "prices": prices,
            "balances": relevant_balances,
            "total_value": total_value,
        }

        with open("current_market_data.json", "w") as f:
            json.dump(data, f, indent=2)

        print("\n✅ Datos guardados en current_market_data.json")

        return data

    except Exception as e:
        print(f"❌ Error obteniendo datos: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(get_current_data())
