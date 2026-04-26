import os
import asyncpg
import logging
from binance import Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


async def update_asset_limits_in_db():
    """
    Obtiene los límites de trading de los activos de Binance y los actualiza en la base de datos.
    """
    load_dotenv()
    logger.info("Iniciando actualización de límites de activos desde Binance...")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")

    db_user = os.getenv("POSTGRES_USER")
    db_pass = os.getenv("POSTGRES_PASSWORD")
    db_name = os.getenv("POSTGRES_DB")
    db_host = os.getenv("POSTGRES_HOST", "db")

    if not all([api_key, api_secret, db_user, db_pass, db_name]):
        logger.error(
            "Faltan variables de entorno para la actualización de límites de activos."
        )
        return

    conn = None
    try:
        client = Client(api_key, api_secret)
        exchange_info = client.get_exchange_info()
        symbols_info = exchange_info.get("symbols", [])
        logger.info(
            f"Se obtuvieron límites para {len(symbols_info)} símbolos desde Binance."
        )

        conn = await asyncpg.connect(
            user=db_user, password=db_pass, database=db_name, host=db_host
        )

        updated_count = 0
        for symbol_info in symbols_info:
            symbol = symbol_info["symbol"]

            # Extraer filtros
            filters = {f["filterType"]: f for f in symbol_info["filters"]}
            price_filter = filters.get("PRICE_FILTER", {})
            lot_size_filter = filters.get("LOT_SIZE", {})
            min_notional_filter = filters.get(
                "MIN_NOTIONAL", filters.get("NOTIONAL")
            )  # NOTIONAL is for market orders

            if not all(
                [
                    price_filter,
                    lot_size_filter,
                    (
                        min_notional_filter
                        and (
                            "minNotional" in min_notional_filter
                            or "notional" in min_notional_filter
                        )
                    ),
                ]
            ):
                continue

            min_notional_val = min_notional_filter.get(
                "minNotional", min_notional_filter.get("notional", 0)
            )

            await conn.execute(
                """
                INSERT INTO asset_limits (symbol, min_price, max_price, tick_size, min_qty, max_qty, step_size, min_notional)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol) DO UPDATE
                SET min_price = $2, max_price = $3, tick_size = $4,
                    min_qty = $5, max_qty = $6, step_size = $7, min_notional = $8,
                    updated_at = NOW();
            """,
                symbol,
                float(price_filter.get("minPrice", 0)),
                float(price_filter.get("maxPrice", 0)),
                float(price_filter.get("tickSize", 0)),
                float(lot_size_filter.get("minQty", 0)),
                float(lot_size_filter.get("maxQty", 0)),
                float(lot_size_filter.get("stepSize", 0)),
                float(min_notional_val),
            )
            updated_count += 1

        logger.info(
            f"{updated_count} límites de activos fueron actualizados en la base de datos."
        )

    except Exception as e:
        logger.error(
            f"Error al actualizar límites de activos en la base de datos: {e}",
            exc_info=True,
        )
    finally:
        if conn:
            await conn.close()
            logger.info("Conexión con la base de datos para límites cerrada.")
