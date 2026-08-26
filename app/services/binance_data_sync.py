#!/usr/bin/env python3
"""
Servicio para sincronizar datos reales de Binance con la base de datos
"""

import os
import asyncio
import asyncpg
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from binance import Client
from app.services.binance_async import AsyncBinanceWrapper

logger = logging.getLogger(__name__)


class BinanceDataSync:
    """Servicio para sincronizar datos de Binance con la base de datos"""

    def __init__(self):
        """Inicializar el servicio de sincronización"""
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        self.db_url = os.getenv(
            "DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"
        )

        # Inicializar cliente de Binance
        self.client = None
        self.async_binance = AsyncBinanceWrapper(
            ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "5"))
        )
        self._initialize_binance_client()

        # Cache para información de símbolos
        self._symbol_info_cache = {}

    def _initialize_binance_client(self):
        """Inicializar cliente de Binance"""
        try:
            if not self.api_key or not self.api_secret:
                logger.warning("Credenciales de Binance no configuradas")
                return

            self.client = Client(self.api_key, self.api_secret)

            # Verificar conexión
            server_time = self.client.get_server_time()
            logger.info(
                f"✅ Cliente de Binance inicializado - Server time: {server_time}"
            )

        except Exception as e:
            logger.error(f"❌ Error inicializando cliente de Binance: {e}")
            self.client = None

    async def get_db_connection(self) -> asyncpg.Connection:
        """Obtener conexión a la base de datos"""
        try:
            return await asyncpg.connect(self.db_url)
        except Exception as e:
            logger.error(f"Error conectando a la base de datos: {e}")
            raise

    async def sync_account_info(self) -> Dict[str, Any]:
        """Sincronizar información de la cuenta de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}

        try:
            # Obtener información de la cuenta
            account_info = await asyncio.to_thread(self.client.get_account)

            # Conectar a la base de datos
            conn = await self.get_db_connection()
            # Asegurar tabla system_config
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_config (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Actualizar configuración del sistema con información de la cuenta
            await conn.execute(
                """
                INSERT INTO system_config (key, value, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """,
                "account_type",
                account_info.get("accountType", "SPOT"),
                "Tipo de cuenta de Binance",
            )

            await conn.execute(
                """
                INSERT INTO system_config (key, value, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """,
                "maker_commission",
                str(account_info.get("makerCommission", 0)),
                "Comisión maker de Binance",
            )

            await conn.execute(
                """
                INSERT INTO system_config (key, value, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """,
                "taker_commission",
                str(account_info.get("takerCommission", 0)),
                "Comisión taker de Binance",
            )

            await conn.close()

            logger.info(
                f"✅ Información de cuenta sincronizada - Tipo: {account_info.get('accountType')}"
            )
            return {
                "status": "success",
                "account_type": account_info.get("accountType"),
                "maker_commission": account_info.get("makerCommission"),
                "taker_commission": account_info.get("takerCommission"),
                "balances_count": len(account_info.get("balances", [])),
            }

        except Exception as e:
            logger.error(f"Error sincronizando información de cuenta: {e}")
            return {"status": "error", "message": str(e)}

    async def sync_balances(self) -> Dict[str, Any]:
        """Sincronizar balances de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}

        try:
            metrics = self._get_pipeline_metrics()
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_account", status="total"
                ).inc()
            self._emit_api_request(endpoint="binance.get_account", status="total")
            # Obtener información de la cuenta
            started_at = datetime.utcnow()
            account_info = await asyncio.to_thread(self.client.get_account)
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_account", status="success"
                ).inc()
                metrics["pipeline_api_request_latency_seconds"].labels(
                    endpoint="binance.get_account"
                ).observe((datetime.utcnow() - started_at).total_seconds())
            self._emit_api_request(endpoint="binance.get_account", status="success")
            balances = account_info.get("balances", [])

            # Conectar a la base de datos
            conn = await self.get_db_connection()

            # Asegurar tabla balances (contrato real de persistencia)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS balances (
                  id SERIAL PRIMARY KEY,
                  asset VARCHAR(20) UNIQUE NOT NULL,
                  amount NUMERIC(20,8) NOT NULL DEFAULT 0,
                  version INTEGER NOT NULL DEFAULT 0,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Tablas antiguas sin UNIQUE en asset rompen ON CONFLICT (asset)
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_balances_asset ON balances (asset);"
            )

            # Insertar balances con saldo
            inserted_count = 0
            total_value_usdt = 0.0

            for balance in balances:
                asset = balance["asset"]
                free = float(balance["free"])
                locked = float(balance["locked"])
                total = free + locked

                if total > 0:
                    await conn.execute(
                        """
                        INSERT INTO balances (asset, amount, version, updated_at)
                        VALUES ($1, $2, 0, CURRENT_TIMESTAMP)
                        ON CONFLICT (asset) DO UPDATE
                            SET amount = EXCLUDED.amount,
                                version = balances.version + 1,
                                updated_at = CURRENT_TIMESTAMP
                        """,
                        asset,
                        total,
                    )

                    # Calcular valor en USDT (solo para resumen operativo)
                    try:
                        if asset in ("USDT", "BUSD"):
                            value_usdt = total
                        else:
                            price_usdt = await self.async_binance.get_price(
                                f"{asset}USDT"
                            )
                            value_usdt = total * price_usdt
                        total_value_usdt += value_usdt
                    except Exception:
                        value_usdt = 0.0

                    inserted_count += 1
                    if metrics:
                        metrics["db_writes_total"].labels(
                            table="balances",
                            operation="upsert",
                            status="ok",
                        ).inc()
                    self._emit_db_write(
                        table="balances", operation="upsert", status="ok"
                    )

            await conn.close()

            logger.info(
                f"✅ Balances sincronizados - {inserted_count} activos con saldo"
            )
            return {
                "status": "success",
                "balances_count": inserted_count,
                "total_value_usdt": total_value_usdt,
            }

        except Exception as e:
            logger.error(f"Error sincronizando balances: {e}")
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_account", status="failure"
                ).inc()
                metrics["pipeline_errors_total"].labels(
                    stage="sync_balances",
                    error_type=self._classify_error_type(str(e)),
                ).inc()
                metrics["db_writes_total"].labels(
                    table="balances", operation="upsert", status="error"
                ).inc()
            err_type = self._classify_error_type(str(e))
            self._emit_api_request(endpoint="binance.get_account", status="failure")
            self._emit_pipeline_error(stage="sync_balances", error_type=err_type)
            self._emit_db_write(table="balances", operation="upsert", status="error")
            return {"status": "error", "message": str(e)}

    async def sync_symbol_info(self, symbols: List[str] = None) -> Dict[str, Any]:
        """Sincronizar información de símbolos de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}

        try:
            # Obtener información del exchange
            exchange_info = await asyncio.to_thread(self.client.get_exchange_info)

            # Conectar a la base de datos
            conn = await self.get_db_connection()

            # Asegurar tabla asset_limits y limpiar
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_limits (
                  symbol VARCHAR(20) PRIMARY KEY,
                  min_price DOUBLE PRECISION NOT NULL,
                  max_price DOUBLE PRECISION NOT NULL,
                  tick_size DOUBLE PRECISION NOT NULL,
                  min_qty DOUBLE PRECISION NOT NULL,
                  max_qty DOUBLE PRECISION NOT NULL,
                  step_size DOUBLE PRECISION NOT NULL,
                  min_notional DOUBLE PRECISION NOT NULL,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await conn.execute("DELETE FROM asset_limits")

            inserted_count = 0

            for symbol_info in exchange_info["symbols"]:
                symbol = symbol_info["symbol"]

                # Filtrar por símbolos específicos si se proporcionan
                if symbols and symbol not in symbols:
                    continue

                # Solo procesar símbolos que terminan en USDT
                if not symbol.endswith("USDT"):
                    continue

                # Extraer filtros
                filters = {f["filterType"]: f for f in symbol_info["filters"]}

                # Obtener información de lot size
                lot_size = filters.get("LOT_SIZE", {})
                min_qty = float(lot_size.get("minQty", "0.001"))
                max_qty = float(lot_size.get("maxQty", "1000000.0"))
                step_size = float(lot_size.get("stepSize", "0.001"))

                # Obtener tick size
                price_filter = filters.get("PRICE_FILTER", {})
                tick_size = float(price_filter.get("tickSize", "0.01"))

                # Obtener min/max price y minNotional si están presentes
                min_price = float(price_filter.get("minPrice", "0"))
                max_price = float(price_filter.get("maxPrice", "0"))
                min_notional_filter = filters.get("MIN_NOTIONAL", {})
                min_notional = float(min_notional_filter.get("minNotional", "10"))

                # Insertar en la base de datos
                await conn.execute(
                    """
                    INSERT INTO asset_limits (symbol, min_price, max_price, tick_size, min_qty, max_qty, step_size, min_notional)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    symbol,
                    min_price,
                    max_price,
                    tick_size,
                    min_qty,
                    max_qty,
                    step_size,
                    min_notional,
                )

                inserted_count += 1

            await conn.close()

            logger.info(
                f"✅ Información de símbolos sincronizada - {inserted_count} símbolos"
            )
            return {"status": "success", "symbols_count": inserted_count}

        except Exception as e:
            logger.error(f"Error sincronizando información de símbolos: {e}")
            return {"status": "error", "message": str(e)}

    async def sync_recent_trades(
        self, symbol: str = "BTCUSDT", limit: int = 100
    ) -> Dict[str, Any]:
        """Sincronizar operaciones recientes de Binance"""
        correlation_id = str(uuid.uuid4())
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}

        try:
            metrics = self._get_pipeline_metrics()
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_recent_trades", status="total"
                ).inc()
            self._emit_api_request(
                endpoint="binance.get_recent_trades", status="total"
            )

            # Obtener operaciones recientes
            started_at = datetime.utcnow()
            trades = await asyncio.to_thread(
                self.client.get_recent_trades, symbol=symbol, limit=limit
            )
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_recent_trades", status="success"
                ).inc()
                metrics["pipeline_api_request_latency_seconds"].labels(
                    endpoint="binance.get_recent_trades"
                ).observe((datetime.utcnow() - started_at).total_seconds())
                metrics["pipeline_events_processed_total"].labels(
                    stage="sync_recent_trades_fetch"
                ).inc(len(trades))
            self._emit_api_request(
                endpoint="binance.get_recent_trades", status="success"
            )
            self._emit_processed("sync_recent_trades_fetch", delta=len(trades))

            logger.info(
                "sync_recent_trades.fetch_completed",
                extra={
                    "correlation_id": correlation_id,
                    "stage": "api_ingest",
                    "symbol": symbol,
                    "result": "ok",
                    "events_count": len(trades),
                },
            )

            # Conectar a la base de datos
            conn = await self.get_db_connection()
            await self._ensure_trades_idempotency_columns(conn)

            inserted_count = 0

            for trade in trades:
                exchange_order_id = str(trade["id"])
                # Un solo INSERT con idempotencia en DB (evita carrera select+insert)
                insert_result = await conn.execute(
                    """
                    INSERT INTO trades (symbol, side, quantity, entry_price, order_id, timestamp, strategy)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (order_id) DO NOTHING
                    """,
                    symbol,
                    "BUY" if trade["isBuyerMaker"] else "SELL",
                    float(trade["qty"]),
                    float(trade["price"]),
                    exchange_order_id,
                    datetime.fromtimestamp(trade["time"] / 1000),
                    "BINANCE_SYNC",
                )

                if insert_result.endswith("1"):
                    inserted_count += 1
                    if metrics:
                        metrics["db_writes_total"].labels(
                            table="trades", operation="insert", status="ok"
                        ).inc()
                    self._emit_db_write(
                        table="trades", operation="insert", status="ok"
                    )
                elif metrics:
                    metrics["pipeline_events_dropped_total"].labels(
                        stage="sync_recent_trades_persist",
                        reason="duplicate_order_id",
                    ).inc()
                    self._emit_dropped(
                        "sync_recent_trades_persist", "duplicate_order_id"
                    )

            await conn.close()

            logger.info(
                f"✅ Operaciones recientes sincronizadas - {inserted_count} nuevas operaciones"
            )
            logger.info(
                "sync_recent_trades.persist_completed",
                extra={
                    "correlation_id": correlation_id,
                    "stage": "persist",
                    "table": "trades",
                    "result": "ok",
                    "rows_inserted": inserted_count,
                    "rows_seen": len(trades),
                },
            )
            return {
                "status": "success",
                "trades_inserted": inserted_count,
                "symbol": symbol,
            }

        except Exception as e:
            logger.error(f"Error sincronizando operaciones recientes: {e}")
            try:
                from app.core.metrics import pipeline_persistence_failures_total
                from app.core.metrics import pipeline_errors_total
                from app.core.metrics import pipeline_api_requests_total

                pipeline_persistence_failures_total.labels(
                    table="trades",
                    reason="sync_recent_trades_error",
                ).inc()
                pipeline_errors_total.labels(
                    stage="sync_recent_trades",
                    error_type=self._classify_error_type(str(e)),
                ).inc()
                pipeline_api_requests_total.labels(
                    endpoint="binance.get_recent_trades", status="failure"
                ).inc()
            except Exception:
                pass
            err_type = self._classify_error_type(str(e))
            self._emit_api_request(
                endpoint="binance.get_recent_trades", status="failure"
            )
            self._emit_pipeline_error(stage="sync_recent_trades", error_type=err_type)
            return {"status": "error", "message": str(e)}

    async def _ensure_trades_idempotency_columns(
        self, conn: asyncpg.Connection
    ) -> None:
        """Asegura columnas/índices mínimos para dedupe de trades sincronizados."""
        await conn.execute(
            """
            ALTER TABLE trades
              ADD COLUMN IF NOT EXISTS order_id VARCHAR(64),
              ADD COLUMN IF NOT EXISTS strategy VARCHAR(50),
              ADD COLUMN IF NOT EXISTS client_order_id VARCHAR(128);
            """
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_order_id ON trades(order_id);"
        )

    def _classify_error_type(self, err: str) -> str:
        err_l = err.lower()
        if "auth" in err_l or "invalid api-key" in err_l or "-2015" in err_l:
            return "auth"
        if "timeout" in err_l or "timed out" in err_l:
            return "timeout"
        if "duplicate key" in err_l or "constraint" in err_l:
            return "constraint"
        if "parse" in err_l or "json" in err_l:
            return "parse"
        return "unknown"

    def _get_pipeline_metrics(self):
        try:
            from app.core.metrics import (
                pipeline_api_requests_total,
                pipeline_api_request_latency_seconds,
                pipeline_events_processed_total,
                pipeline_events_dropped_total,
                db_writes_total,
            )

            return {
                "pipeline_api_requests_total": pipeline_api_requests_total,
                "pipeline_api_request_latency_seconds": pipeline_api_request_latency_seconds,
                "pipeline_events_processed_total": pipeline_events_processed_total,
                "pipeline_events_dropped_total": pipeline_events_dropped_total,
                "db_writes_total": db_writes_total,
            }
        except Exception:
            return None

    def _emit_db_write(self, *, table: str, operation: str, status: str) -> None:
        try:
            from app.core.pipeline_metrics_sidecar import record_db_write

            record_db_write(table=table, operation=operation, status=status)
        except Exception:
            pass

    def _emit_processed(self, stage: str, delta: float = 1.0) -> None:
        try:
            from app.core.pipeline_metrics_sidecar import bump_labeled_counter

            bump_labeled_counter(
                "pipeline_events_processed_total", delta=delta, stage=stage
            )
            bump_labeled_counter(
                "gridbot_items_processed_total", delta=delta, stage=stage
            )
        except Exception:
            pass

    def _emit_dropped(self, stage: str, reason: str, delta: float = 1.0) -> None:
        try:
            from app.core.pipeline_metrics_sidecar import bump_labeled_counter

            bump_labeled_counter(
                "pipeline_events_dropped_total", delta=delta, stage=stage, reason=reason
            )
            bump_labeled_counter(
                "gridbot_items_dropped_total", delta=delta, stage=stage, reason=reason
            )
        except Exception:
            pass

    def _emit_pipeline_error(self, stage: str, error_type: str) -> None:
        try:
            from app.core.pipeline_metrics_sidecar import record_pipeline_error

            record_pipeline_error(stage=stage, error_type=error_type)
        except Exception:
            pass

    def _emit_api_request(self, *, endpoint: str, status: str) -> None:
        try:
            from app.core.pipeline_metrics_sidecar import record_api_request

            record_api_request(endpoint=endpoint, status=status)
        except Exception:
            pass

    async def sync_klines_data(
        self, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 100
    ) -> Dict[str, Any]:
        """Sincronizar datos de velas (klines) de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}

        try:
            # Obtener datos de velas
            klines = await self.async_binance.get_klines(symbol, interval, limit)

            # Conectar a la base de datos
            conn = await self.get_db_connection()

            # Crear tabla temporal para klines si no existe
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS klines_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    interval VARCHAR(10) NOT NULL,
                    open_time TIMESTAMP NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    close_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Limpiar datos anteriores para este símbolo e intervalo
            await conn.execute(
                """
                DELETE FROM klines_data WHERE symbol = $1 AND interval = $2
            """,
                symbol,
                interval,
            )

            inserted_count = 0

            for kline in klines:
                await conn.execute(
                    """
                    INSERT INTO klines_data (symbol, interval, open_time, open_price, high_price, low_price, close_price, volume, close_time)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    symbol,
                    interval,
                    datetime.fromtimestamp(kline[0] / 1000),
                    float(kline[1]),
                    float(kline[2]),
                    float(kline[3]),
                    float(kline[4]),
                    float(kline[5]),
                    datetime.fromtimestamp(kline[6] / 1000),
                )

                inserted_count += 1

            await conn.close()

            logger.info(
                f"✅ Datos de velas sincronizados - {inserted_count} registros para {symbol}"
            )
            return {
                "status": "success",
                "klines_inserted": inserted_count,
                "symbol": symbol,
                "interval": interval,
            }

        except Exception as e:
            logger.error(f"Error sincronizando datos de velas: {e}")
            return {"status": "error", "message": str(e)}

    async def sync_performance_metrics(self) -> Dict[str, Any]:
        """Sincronizar métricas de rendimiento desde Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}

        try:
            metrics = self._get_pipeline_metrics()
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_account", status="total"
                ).inc()
            self._emit_api_request(endpoint="binance.get_account", status="total")
            # Obtener información de la cuenta
            started_at = datetime.utcnow()
            account_info = await asyncio.to_thread(self.client.get_account)
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_account", status="success"
                ).inc()
                metrics["pipeline_api_request_latency_seconds"].labels(
                    endpoint="binance.get_account"
                ).observe((datetime.utcnow() - started_at).total_seconds())
            self._emit_api_request(endpoint="binance.get_account", status="success")

            # Calcular métricas básicas
            total_trades = 0
            total_profit = 0.0
            total_value_usdt = 0.0

            # Calcular valor total del portfolio
            for balance in account_info.get("balances", []):
                asset = balance["asset"]
                free = float(balance["free"])
                locked = float(balance["locked"])
                total = free + locked

                if total > 0:
                    if asset == "USDT":
                        value_usdt = total
                    elif asset == "BUSD":
                        value_usdt = total
                    else:
                        try:
                            ticker = self.client.get_symbol_ticker(
                                symbol=f"{asset}USDT"
                            )
                            price_usdt = float(ticker["price"])
                            value_usdt = total * price_usdt
                        except:
                            value_usdt = 0.0

                    total_value_usdt += value_usdt

            # Conectar a la base de datos
            conn = await self.get_db_connection()

            # Obtener estadísticas de operaciones
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN profit_loss > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN profit_loss < 0 THEN 1 END) as losing_trades,
                    COALESCE(SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END), 0) as total_profit,
                    COALESCE(SUM(CASE WHEN profit_loss < 0 THEN ABS(profit_loss) ELSE 0 END), 0) as total_loss
                FROM trades
                WHERE strategy != 'BINANCE_SYNC'
            """)

            if stats:
                total_trades = stats["total_trades"] or 0
                winning_trades = stats["winning_trades"] or 0
                losing_trades = stats["losing_trades"] or 0
                total_profit = float(stats["total_profit"] or 0)
                total_loss = float(stats["total_loss"] or 0)

                win_rate = (
                    (winning_trades / total_trades * 100) if total_trades > 0 else 0
                )

                # Fila agregada id=1 (ON CONFLICT DO NOTHING sin PK no es dedupe en PG)
                ts = datetime.now()
                await conn.execute(
                    """
                    INSERT INTO performance_metrics (
                        id, total_trades, winning_trades, losing_trades,
                        total_profit, total_loss, win_rate, timestamp
                    )
                    VALUES (1, $1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        total_trades = EXCLUDED.total_trades,
                        winning_trades = EXCLUDED.winning_trades,
                        losing_trades = EXCLUDED.losing_trades,
                        total_profit = EXCLUDED.total_profit,
                        total_loss = EXCLUDED.total_loss,
                        win_rate = EXCLUDED.win_rate,
                        timestamp = EXCLUDED.timestamp
                    """,
                    total_trades,
                    winning_trades,
                    losing_trades,
                    total_profit,
                    total_loss,
                    win_rate,
                    ts,
                )
                if metrics:
                    metrics["db_writes_total"].labels(
                        table="performance_metrics",
                        operation="insert",
                        status="ok",
                    ).inc()
                self._emit_db_write(
                    table="performance_metrics", operation="insert", status="ok"
                )

            await conn.close()

            logger.info("✅ Métricas de rendimiento sincronizadas")
            return {
                "status": "success",
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "total_loss": total_loss,
                "portfolio_value_usdt": total_value_usdt,
            }

        except Exception as e:
            logger.error(f"Error sincronizando métricas de rendimiento: {e}")
            if metrics:
                metrics["pipeline_api_requests_total"].labels(
                    endpoint="binance.get_account", status="failure"
                ).inc()
                metrics["pipeline_errors_total"].labels(
                    stage="sync_performance_metrics",
                    error_type=self._classify_error_type(str(e)),
                ).inc()
                metrics["db_writes_total"].labels(
                    table="performance_metrics",
                    operation="insert",
                    status="error",
                ).inc()
            err_type = self._classify_error_type(str(e))
            self._emit_api_request(endpoint="binance.get_account", status="failure")
            self._emit_pipeline_error(
                stage="sync_performance_metrics", error_type=err_type
            )
            self._emit_db_write(
                table="performance_metrics", operation="insert", status="error"
            )
            return {"status": "error", "message": str(e)}

    async def _get_symbol_info(self, asset: str) -> Optional[Dict[str, Any]]:
        """Obtener información de un símbolo específico"""
        try:
            if not self.client:
                return None

            symbol = f"{asset}USDT"

            if symbol not in self._symbol_info_cache:
                exchange_info = self.client.get_exchange_info()
                for s in exchange_info["symbols"]:
                    if s["symbol"] == symbol:
                        filters = {f["filterType"]: f for f in s["filters"]}
                        self._symbol_info_cache[symbol] = {
                            "symbol": s["symbol"],
                            "baseAsset": s["baseAsset"],
                            "quoteAsset": s["quoteAsset"],
                            "stepSize": float(
                                filters.get("LOT_SIZE", {}).get("stepSize", "0.001")
                            ),
                            "minQty": float(
                                filters.get("LOT_SIZE", {}).get("minQty", "0.001")
                            ),
                            "maxQty": float(
                                filters.get("LOT_SIZE", {}).get("maxQty", "1000000.0")
                            ),
                            "tickSize": float(
                                filters.get("PRICE_FILTER", {}).get("tickSize", "0.01")
                            ),
                            "minPrice": float(
                                filters.get("PRICE_FILTER", {}).get("minPrice", "0")
                            ),
                            "maxPrice": float(
                                filters.get("PRICE_FILTER", {}).get("maxPrice", "0")
                            ),
                            "minNotional": float(
                                filters.get("MIN_NOTIONAL", {}).get("minNotional", "10")
                            ),
                        }
                        break

            return self._symbol_info_cache.get(symbol)

        except Exception as e:
            logger.error(f"Error obteniendo información del símbolo {asset}: {e}")
            return None

    async def full_sync(self) -> Dict[str, Any]:
        """Realizar sincronización completa de todos los datos"""
        logger.info("🔄 Iniciando sincronización completa de datos de Binance")

        results = {}

        # 1. Sincronizar información de cuenta
        results["account_info"] = await self.sync_account_info()

        # 2. Sincronizar balances
        results["balances"] = await self.sync_balances()

        # 3. Sincronizar información de símbolos principales
        main_symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "SOLUSDT"]
        results["symbol_info"] = await self.sync_symbol_info(main_symbols)

        # 4. Sincronizar operaciones recientes
        results["recent_trades"] = await self.sync_recent_trades("BTCUSDT", 50)

        # 5. Sincronizar datos de velas
        results["klines"] = await self.sync_klines_data("BTCUSDT", "1h", 24)

        # 6. Sincronizar métricas de rendimiento
        results["performance"] = await self.sync_performance_metrics()

        logger.info("✅ Sincronización completa finalizada")
        return results


# Instancia global del servicio
binance_sync = BinanceDataSync()
