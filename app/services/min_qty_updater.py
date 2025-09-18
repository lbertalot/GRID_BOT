import asyncpg

async def create_asset_min_qty_table():
    db_user = os.getenv("POSTGRES_USER")
    db_pass = os.getenv("POSTGRES_PASSWORD")
    db_name = os.getenv("POSTGRES_DB")
    db_host = os.getenv("POSTGRES_HOST", "db")
    conn = await asyncpg.connect(user=db_user, password=db_pass, database=db_name, host=db_host)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS asset_min_qty (
            symbol VARCHAR(20) PRIMARY KEY,
            min_qty NUMERIC NOT NULL,
            calculado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    ''')
    await conn.close()

import math
from binance.client import Client
from dotenv import load_dotenv
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "grid_config_optimized.json")

async def update_min_qty_in_db():
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
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
    for symbol, data in config.items():
        if symbol.startswith("_"):
            continue
        row = await conn.fetchrow("SELECT min_notional, step_size FROM asset_limits WHERE symbol = $1", symbol)
        if not row:
            continue
        min_notional = float(row["min_notional"])
        step_size = float(row["step_size"])
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
        except Exception:
            continue
        cantidad_min = math.ceil(min_notional / price / step_size) * step_size
        cantidad_min = round(cantidad_min, int(abs(math.log10(step_size))))
        await conn.execute('''
            INSERT INTO asset_min_qty (symbol, min_qty, calculado_en)
            VALUES ($1, $2, NOW())
            ON CONFLICT (symbol) DO UPDATE SET min_qty = $2, calculado_en = NOW();
        ''', symbol, cantidad_min)
    await conn.close()

async def update_min_qty_in_db_and_config():
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
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
    for symbol, data in config.items():
        if symbol.startswith("_"):
            continue
        row = await conn.fetchrow("SELECT min_notional, step_size FROM asset_limits WHERE symbol = $1", symbol)
        if not row:
            continue
        min_notional = float(row["min_notional"])
        step_size = float(row["step_size"])
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
        except Exception:
            continue
        cantidad_min = math.ceil(min_notional / price / step_size) * step_size
        cantidad_min = round(cantidad_min, int(abs(math.log10(step_size))))
        await conn.execute('''
            INSERT INTO asset_min_qty (symbol, min_qty, calculado_en)
            VALUES ($1, $2, NOW())
            ON CONFLICT (symbol) DO UPDATE SET min_qty = $2, calculado_en = NOW();
        ''', symbol, cantidad_min)
        # Actualizar config
        config[symbol]["quantity"] = cantidad_min
    await conn.close()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print("Archivo de configuración actualizado automáticamente con las cantidades mínimas.") 