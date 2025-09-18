import os
import asyncpg
import asyncio
import logging
from binance import Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

async def update_balances_in_db():
    """
    Obtiene los balances de Binance y los actualiza en la base de datos.
    Se ejecuta durante el evento de inicio de la aplicación FastAPI.
    """
    load_dotenv()
    logger.info("Iniciando actualización de balances desde Binance...")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    
    db_user = os.getenv("POSTGRES_USER")
    db_pass = os.getenv("POSTGRES_PASSWORD")
    db_name = os.getenv("POSTGRES_DB")
    db_host = os.getenv("POSTGRES_HOST", "db")

    if not all([api_key, api_secret, db_user, db_pass, db_name]):
        logger.error("Faltan variables de entorno para la actualización de balances. Verifique el archivo .env.")
        return

    # Conexión a Binance
    try:
        client = Client(api_key, api_secret)
        account_info = client.get_account()
        balances = account_info.get("balances", [])
        logger.info(f"Se obtuvieron {len(balances)} balances desde Binance.")
    except Exception as e:
        logger.error(f"Error al conectar con Binance API: {e}")
        return

    # Conexión a la base de datos
    conn = None
    try:
        conn = await asyncpg.connect(user=db_user, password=db_pass, database=db_name, host=db_host)
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS balances (
                asset VARCHAR(20) PRIMARY KEY,
                free NUMERIC,
                locked NUMERIC,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        ''')

        updated_count = 0
        for balance in balances:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            
            if free > 0 or locked > 0:
                await conn.execute('''
                    INSERT INTO balances (asset, free, locked) 
                    VALUES ($1, $2, $3)
                    ON CONFLICT (asset) DO UPDATE
                    SET free = $2, locked = $3, updated_at = NOW();
                ''', asset, free, locked)
                updated_count += 1
        
        logger.info(f"{updated_count} balances con saldo fueron actualizados en la base de datos.")

    except Exception as e:
        logger.error(f"Error al actualizar balances en la base de datos: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Conexión con la base de datos cerrada.") 