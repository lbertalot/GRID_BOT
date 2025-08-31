from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime
from app.services.binance_data_sync import binance_sync

router = APIRouter(prefix="/api/v1/binance", tags=["Binance Sync"])


@router.post("/sync/account")
async def sync_binance_account():
    try:
        result = await binance_sync.sync_account_info()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/sync/balances")
async def sync_binance_balances():
    try:
        result = await binance_sync.sync_balances()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/sync/symbols")
async def sync_binance_symbols():
    try:
        result = await binance_sync.sync_symbol_info()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/sync/trades")
async def sync_binance_trades():
    try:
        result = await binance_sync.sync_recent_trades("BTCUSDT", 50)
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/sync/klines")
async def sync_binance_klines():
    try:
        result = await binance_sync.sync_klines_data("BTCUSDT", "1h", 24)
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/sync/performance")
async def sync_binance_performance():
    try:
        result = await binance_sync.sync_performance_metrics()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/sync/full")
async def sync_binance_full():
    try:
        result = await binance_sync.full_sync()
        return {
            "status": "success",
            "message": "Sincronización completa finalizada",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.get("/data/account")
async def get_binance_account_data():
    try:
        import asyncpg
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        rows = await conn.fetch(
            """
            SELECT key, value, description 
            FROM system_config 
            WHERE key IN ('account_type', 'maker_commission', 'taker_commission')
            ORDER BY key
            """
        )
        await conn.close()
        return {
            "status": "success",
            "data": {
                "account_info": {row['key']: row['value'] for row in rows},
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.get("/data/balances")
async def get_binance_balances_data():
    try:
        import asyncpg
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        rows = await conn.fetch(
            """
            SELECT symbol, min_qty, max_qty, step_size, tick_size, created_at
            FROM asset_limits 
            ORDER BY symbol
            """
        )
        await conn.close()
        return {
            "status": "success",
            "data": {
                "balances": [dict(r) for r in rows],
                "count": len(rows),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.get("/data/trades")
async def get_binance_trades_data():
    try:
        import asyncpg
        import os
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        rows = await conn.fetch(
            """
            SELECT symbol, side, quantity, entry_price, timestamp, strategy
            FROM trades 
            ORDER BY timestamp DESC 
            LIMIT 20
            """
        )
        await conn.close()
        return {
            "status": "success",
            "data": {
                "trades": [dict(r) for r in rows],
                "count": len(rows),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.get("/data/performance")
async def get_binance_performance_data():
    try:
        import asyncpg
        import os
        row = None
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        row = await conn.fetchrow(
            """
            SELECT total_trades, winning_trades, losing_trades, total_profit, total_loss, win_rate, timestamp
            FROM performance_metrics 
            ORDER BY timestamp DESC 
            LIMIT 1
            """
        )
        await conn.close()
        return {
            "status": "success",
            "data": {
                "performance": dict(row) if row else {},
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


