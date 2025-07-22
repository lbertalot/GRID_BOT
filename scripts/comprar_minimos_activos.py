import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# Activos a comprar
ACTIVOS = ["ANIME", "GPS", "GUN", "SIGN", "SPK", "HOME", "HUMA"]
MIN_NOTIONAL = 5.0  # Valor mínimo en USDT por operación
MARGEN = 1.02       # 2% de margen para evitar rechazos por fluctuaciones

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

if not api_key or not api_secret:
    print("❌ Faltan credenciales de Binance en las variables de entorno.")
    exit(1)

client = Client(api_key, api_secret)

for asset in ACTIVOS:
    symbol = f"{asset}USDT"
    try:
        # Obtener precio actual
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker["price"])
        # Calcular cantidad mínima
        min_qty = (MIN_NOTIONAL * MARGEN) / price
        # Ajustar a stepSize
        info = client.get_symbol_info(symbol)
        step_size = None
        for f in info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                step_size = float(f["stepSize"])
                break
        if step_size:
            precision = int(-round((round(step_size, 10)).as_integer_ratio()[1]).bit_length() + 1)
            min_qty = round((min_qty // step_size) * step_size, abs(precision))
        min_qty = float(f"{min_qty:.8f}")
        # Ejecutar compra de mercado
        print(f"Comprando {min_qty} {asset} (≈{min_qty*price:.2f} USDT) en {symbol}...")
        order = client.order_market_buy(symbol=symbol, quantity=min_qty)
        print(f"✅ Orden ejecutada: {order['orderId']} | {min_qty} {asset} @ {price} USDT")
        time.sleep(2)  # Pausa para evitar rate limits
    except BinanceAPIException as e:
        print(f"❌ Error en {symbol}: {e.message}")
    except Exception as e:
        print(f"❌ Error inesperado en {symbol}: {e}") 