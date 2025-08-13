#!/usr/bin/env python3
"""
Servicio para sincronizar datos reales de Binance con la base de datos
"""

import os
import asyncio
import asyncpg
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from binance import Client
from binance.exceptions import BinanceAPIException
import json

logger = logging.getLogger(__name__)

class BinanceDataSync:
    """Servicio para sincronizar datos de Binance con la base de datos"""
    
    def __init__(self):
        """Inicializar el servicio de sincronización"""
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        self.db_url = os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot")
        
        # Inicializar cliente de Binance
        self.client = None
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
            logger.info(f"✅ Cliente de Binance inicializado - Server time: {server_time}")
            
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
            account_info = self.client.get_account()
            
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
            await conn.execute("""
                INSERT INTO system_config (key, value, description) 
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET 
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """, "account_type", account_info.get("accountType", "SPOT"), "Tipo de cuenta de Binance")
            
            await conn.execute("""
                INSERT INTO system_config (key, value, description) 
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET 
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """, "maker_commission", str(account_info.get("makerCommission", 0)), "Comisión maker de Binance")
            
            await conn.execute("""
                INSERT INTO system_config (key, value, description) 
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET 
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """, "taker_commission", str(account_info.get("takerCommission", 0)), "Comisión taker de Binance")
            
            await conn.close()
            
            logger.info(f"✅ Información de cuenta sincronizada - Tipo: {account_info.get('accountType')}")
            return {
                "status": "success",
                "account_type": account_info.get("accountType"),
                "maker_commission": account_info.get("makerCommission"),
                "taker_commission": account_info.get("takerCommission"),
                "balances_count": len(account_info.get("balances", []))
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
            # Obtener información de la cuenta
            account_info = self.client.get_account()
            balances = account_info.get("balances", [])
            
            # Conectar a la base de datos
            conn = await self.get_db_connection()
            
            # Asegurar tabla asset_limits (por si migraciones no corrieron)
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
            # Limpiar balances anteriores
            await conn.execute("DELETE FROM asset_limits")
            
            # Insertar balances con saldo
            inserted_count = 0
            total_value_usdt = 0.0
            
            for balance in balances:
                asset = balance["asset"]
                free = float(balance["free"])
                locked = float(balance["locked"])
                total = free + locked
                
                if total > 0:
                    # Obtener información del símbolo si es posible
                    symbol_info = await self._get_symbol_info(asset)
                    
                    if symbol_info:
                        await conn.execute(
                            """
                            INSERT INTO asset_limits (symbol, min_price, max_price, tick_size, min_qty, max_qty, step_size, min_notional)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            f"{asset}USDT",
                            symbol_info.get("minPrice", 0.0),
                            symbol_info.get("maxPrice", 0.0),
                            symbol_info.get("tickSize", 0.01),
                            symbol_info.get("minQty", 0.001),
                            symbol_info.get("maxQty", 1000000.0),
                            symbol_info.get("stepSize", 0.001),
                            symbol_info.get("minNotional", 10.0),
                        )
                        
                        # Calcular valor en USDT
                        try:
                            if asset == "USDT":
                                value_usdt = total
                            elif asset == "BUSD":
                                value_usdt = total
                            else:
                                ticker = self.client.get_symbol_ticker(symbol=f"{asset}USDT")
                                price_usdt = float(ticker["price"])
                                value_usdt = total * price_usdt
                            
                            total_value_usdt += value_usdt
                        except:
                            value_usdt = 0.0
                        
                        inserted_count += 1
            
            await conn.close()
            
            logger.info(f"✅ Balances sincronizados - {inserted_count} activos con saldo")
            return {
                "status": "success",
                "balances_count": inserted_count,
                "total_value_usdt": total_value_usdt
            }
            
        except Exception as e:
            logger.error(f"Error sincronizando balances: {e}")
            return {"status": "error", "message": str(e)}
    
    async def sync_symbol_info(self, symbols: List[str] = None) -> Dict[str, Any]:
        """Sincronizar información de símbolos de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}
        
        try:
            # Obtener información del exchange
            exchange_info = self.client.get_exchange_info()
            
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
                    symbol, min_price, max_price, tick_size, min_qty, max_qty, step_size, min_notional
                )
                
                inserted_count += 1
            
            await conn.close()
            
            logger.info(f"✅ Información de símbolos sincronizada - {inserted_count} símbolos")
            return {
                "status": "success",
                "symbols_count": inserted_count
            }
            
        except Exception as e:
            logger.error(f"Error sincronizando información de símbolos: {e}")
            return {"status": "error", "message": str(e)}
    
    async def sync_recent_trades(self, symbol: str = "BTCUSDT", limit: int = 100) -> Dict[str, Any]:
        """Sincronizar operaciones recientes de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}
        
        try:
            # Obtener operaciones recientes
            trades = self.client.get_recent_trades(symbol=symbol, limit=limit)
            
            # Conectar a la base de datos
            conn = await self.get_db_connection()
            
            inserted_count = 0
            
            for trade in trades:
                # Verificar si la operación ya existe
                existing = await conn.fetchrow("""
                    SELECT id FROM trades WHERE order_id = $1
                """, str(trade["id"]))
                
                if not existing:
                    # Insertar nueva operación
                    await conn.execute("""
                        INSERT INTO trades (symbol, side, quantity, entry_price, order_id, timestamp, strategy)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    symbol,
                    "BUY" if trade["isBuyerMaker"] else "SELL",
                    float(trade["qty"]),
                    float(trade["price"]),
                    str(trade["id"]),
                    datetime.fromtimestamp(trade["time"] / 1000),
                    "BINANCE_SYNC"
                    )
                    
                    inserted_count += 1
            
            await conn.close()
            
            logger.info(f"✅ Operaciones recientes sincronizadas - {inserted_count} nuevas operaciones")
            return {
                "status": "success",
                "trades_inserted": inserted_count,
                "symbol": symbol
            }
            
        except Exception as e:
            logger.error(f"Error sincronizando operaciones recientes: {e}")
            return {"status": "error", "message": str(e)}
    
    async def sync_klines_data(self, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 100) -> Dict[str, Any]:
        """Sincronizar datos de velas (klines) de Binance"""
        if not self.client:
            logger.warning("Cliente de Binance no disponible")
            return {"status": "error", "message": "Cliente de Binance no disponible"}
        
        try:
            # Obtener datos de velas
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
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
            await conn.execute("""
                DELETE FROM klines_data WHERE symbol = $1 AND interval = $2
            """, symbol, interval)
            
            inserted_count = 0
            
            for kline in klines:
                await conn.execute("""
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
                datetime.fromtimestamp(kline[6] / 1000)
                )
                
                inserted_count += 1
            
            await conn.close()
            
            logger.info(f"✅ Datos de velas sincronizados - {inserted_count} registros para {symbol}")
            return {
                "status": "success",
                "klines_inserted": inserted_count,
                "symbol": symbol,
                "interval": interval
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
            # Obtener información de la cuenta
            account_info = self.client.get_account()
            
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
                            ticker = self.client.get_symbol_ticker(symbol=f"{asset}USDT")
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
                
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                # Actualizar métricas de rendimiento
                await conn.execute("""
                    INSERT INTO performance_metrics (total_trades, winning_trades, losing_trades, total_profit, total_loss, win_rate, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                """,
                total_trades,
                winning_trades,
                losing_trades,
                total_profit,
                total_loss,
                win_rate,
                datetime.now()
                )
            
            await conn.close()
            
            logger.info(f"✅ Métricas de rendimiento sincronizadas")
            return {
                "status": "success",
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "total_loss": total_loss,
                "portfolio_value_usdt": total_value_usdt
            }
            
        except Exception as e:
            logger.error(f"Error sincronizando métricas de rendimiento: {e}")
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
                            "stepSize": float(filters.get("LOT_SIZE", {}).get("stepSize", "0.001")),
                            "minQty": float(filters.get("LOT_SIZE", {}).get("minQty", "0.001")),
                            "maxQty": float(filters.get("LOT_SIZE", {}).get("maxQty", "1000000.0")),
                            "tickSize": float(filters.get("PRICE_FILTER", {}).get("tickSize", "0.01")),
                            "minPrice": float(filters.get("PRICE_FILTER", {}).get("minPrice", "0")),
                            "maxPrice": float(filters.get("PRICE_FILTER", {}).get("maxPrice", "0")),
                            "minNotional": float(filters.get("MIN_NOTIONAL", {}).get("minNotional", "10")),
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