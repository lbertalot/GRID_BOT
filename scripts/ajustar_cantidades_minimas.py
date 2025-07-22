import os
import sys
import json
import math
import asyncpg
from dotenv import load_dotenv
from binance.client import Client

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "grid_config_optimized.json")

async def ajustar_cantidades():
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    db_user = os.getenv("POSTGRES_USER")
    db_pass = os.getenv("POSTGRES_PASSWORD")
    db_name = os.getenv("POSTGRES_DB")
    db_host = os.getenv("POSTGRES_HOST", "db")

    if not all([api_key, api_secret, db_user, db_pass, db_name]):
        print("Error: Faltan variables de entorno necesarias.")
        return

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    client = Client(api_key, api_secret)
    conn = await asyncpg.connect(user=db_user, password=db_pass, database=db_name, host=db_host)

    print("Propuesta de cantidades mínimas para cumplir con el valor nocional mínimo de Binance:")
    cambios = {}
    for symbol, data in config.items():
        if symbol.startswith("_"):
            continue
        # Obtener límites desde la base de datos
        row = await conn.fetchrow("SELECT min_notional, step_size FROM asset_limits WHERE symbol = $1", symbol)
        if not row:
            print(f"  - {symbol}: No se encontraron límites en la base de datos. Se omite.")
            continue
        min_notional = float(row["min_notional"])
        step_size = float(row["step_size"])
        # Obtener precio actual
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
        except Exception as e:
            print(f"  - {symbol}: Error obteniendo precio: {e}. Se omite.")
            continue
        # Calcular cantidad mínima
        cantidad_min = math.ceil(min_notional / price / step_size) * step_size
        cantidad_min = round(cantidad_min, int(abs(math.log10(step_size))))
        actual = data["quantity"]
        print(f"  - {symbol}: cantidad actual = {actual}, cantidad mínima sugerida = {cantidad_min} (min_notional={min_notional}, step_size={step_size}, precio={price})")
        cambios[symbol] = cantidad_min
    await conn.close()

    # Preguntar si se desea actualizar el archivo
    resp = input("\n¿Deseas actualizar el archivo grid_config_optimized.json con estas cantidades? (s/n): ").strip().lower()
    if resp == "s":
        for symbol, cantidad in cambios.items():
            config[symbol]["quantity"] = cantidad
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print("Archivo actualizado correctamente.")
    else:
        print("No se realizaron cambios en el archivo.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(ajustar_cantidades()) 