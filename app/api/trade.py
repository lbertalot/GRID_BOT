from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from binance import Client
import os
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.scheduler.grid_job import update_grid_config, get_grid_config
from app.services.binance_service import BinanceService
from sqlalchemy.orm import Session
from app.models.trade import Trade
from datetime import datetime
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.trade import Trade
from typing import List, Optional
from fastapi import Query
from app.services.telegram_alert import send_telegram_alert
from app.core.auth import require_auth
from app.schemas.validation import OrderRequest, GridParams

router = APIRouter()

# Instancia global del servicio de Binance
binance_service = BinanceService()

def log_trade(
    db: Session,
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    exit_price: Optional[float] = None,
    profit_loss: Optional[float] = None,
    timestamp: Optional[datetime] = None
) -> Trade:
    trade = Trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        profit_loss=profit_loss,
        timestamp=timestamp or datetime.utcnow()
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade

@router.get("/price/{symbol}")
def get_price(symbol: str):
    try:
        price = binance_service.get_current_price(symbol.upper())
        return {"symbol": symbol.upper(), "price": price}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Binance: {e}")

@router.get("/balances")
def get_balances():
    try:
        account_info = binance_service.get_account_info()
        balances = {
            b["asset"]: float(b["free"])
            for b in account_info["balances"]
            if float(b["free"]) > 0
        }
        return balances
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando balances: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/trades")
def get_trades(
    symbol: Optional[str] = Query(None, description="Filtrar por símbolo"),
    side: Optional[str] = Query(None, description="Filtrar por lado (BUY/SELL)"),
    limit: int = Query(10, ge=1, le=100, description="Número de resultados"),
    offset: int = Query(0, ge=0, description="Número de resultados a saltar"),
    db: Session = Depends(get_db)
):
    query = db.query(Trade)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    if side:
        query = query.filter(Trade.side == side.upper())
    trades = query.offset(offset).limit(limit).all()
    return trades

@router.post("/order")
def place_order(
    order: OrderRequest = Body(...), 
    db: Session = Depends(get_db),
    api_key: str = Depends(require_auth)
):
    api_key_binance = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key_binance, api_secret)
    try:
        if order.type == 'MARKET':
            if order.side == 'BUY':
                result = client.order_market_buy(symbol=order.symbol.upper(), quantity=order.quantity)
            elif order.side == 'SELL':
                result = client.order_market_sell(symbol=order.symbol.upper(), quantity=order.quantity)
            else:
                raise HTTPException(status_code=400, detail="Lado de orden inválido (debe ser BUY o SELL)")
        elif order.type == 'LIMIT':
            if not order.price:
                raise HTTPException(status_code=400, detail="Precio requerido para órdenes LIMIT")
            if order.side == 'BUY':
                result = client.order_limit_buy(symbol=order.symbol.upper(), quantity=order.quantity, price=str(order.price), timeInForce='GTC')
            elif order.side == 'SELL':
                result = client.order_limit_sell(symbol=order.symbol.upper(), quantity=order.quantity, price=str(order.price), timeInForce='GTC')
            else:
                raise HTTPException(status_code=400, detail="Lado de orden inválido (debe ser BUY o SELL)")
        else:
            raise HTTPException(status_code=400, detail="Tipo de orden inválido (debe ser MARKET o LIMIT)")
        # Registro en base de datos
        log_trade(
            db=db,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            entry_price=float(result['fills'][0]['price']) if 'fills' in result and result['fills'] else None
        )
        send_telegram_alert(f"✅ Orden ejecutada: {order.side} {order.quantity} {order.symbol} ({order.type})")
        return {"order": result}
    except Exception as e:
        send_telegram_alert(f"❌ Error ejecutando orden: {order.side} {order.quantity} {order.symbol} - {e}")
        raise HTTPException(status_code=400, detail=f"Error ejecutando orden: {e}")

@router.post("/run_grid")
def run_grid(
    params: GridParams = Body(...),
    api_key: str = Depends(require_auth)
):
    api_key_binance = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key_binance, api_secret)
    try:
        # 1. Calcular niveles de la grilla
        grid_levels = calculate_grid_levels(params.min_price, params.max_price, params.grids)
        # 2. Obtener precio actual
        ticker = client.get_symbol_ticker(symbol=params.symbol.upper())
        current_price = float(ticker["price"])
        # 3. Decidir acción
        decision = decide_grid_action(current_price, grid_levels, params.last_action)
        if decision["action"]:
            # 4. Ejecutar orden
            if decision["action"] == "BUY":
                result = client.order_market_buy(symbol=params.symbol.upper(), quantity=params.quantity)
            else:
                result = client.order_market_sell(symbol=params.symbol.upper(), quantity=params.quantity)
            return {"decision": decision, "order_result": result}
        else:
            return {"decision": decision, "message": "No se ejecutó ninguna orden"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en grid trading: {e}")

@router.get("/grid_config")
def get_grid_config_endpoint():
    return get_grid_config()

@router.post("/grid_config")
def update_grid_config_endpoint(
    config: GridParams = Body(...),
    api_key: str = Depends(require_auth)
):
    update_grid_config(config.dict())
    return {"message": "Configuración actualizada", "config": config.dict()}
