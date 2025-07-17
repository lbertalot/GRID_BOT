from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from binance import Client
import os
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.scheduler.grid_job import update_grid_config, get_grid_config
from app.services.binance_service import log_trade
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.trade import Trade
from typing import List, Optional
from fastapi import Query

router = APIRouter()

class OrderRequest(BaseModel):
    symbol: str
    side: str  # 'BUY' o 'SELL'
    quantity: float
    type: str = 'MARKET'  # 'MARKET' o 'LIMIT'
    price: float | None = None  # Solo para órdenes LIMIT

class GridParams(BaseModel):
    symbol: str = 'BTCUSDT'
    min_price: float = 20000
    max_price: float = 30000
    grids: int = 5
    quantity: float = 0.001
    last_action: str | None = None

# Utilidad síncrona para ejemplo simple (puedes migrar a async si lo deseas)
def get_binance_price(symbol: str) -> float:
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Binance: {e}")

@router.get("/price/{symbol}")
def get_price(symbol: str):
    price = get_binance_price(symbol.upper())
    return {"symbol": symbol.upper(), "price": price}

@router.get("/balances")
def get_balances():
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
    try:
        account = client.get_account()
        balances = {
            b["asset"]: float(b["free"])
            for b in account["balances"]
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

@router.post("/order")
def place_order(order: OrderRequest = Body(...), db=Depends(get_db)):
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
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
        return {"order": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error ejecutando orden: {e}")

@router.post("/run_grid")
def run_grid(params: GridParams = Body(...)):
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
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
def api_get_grid_config():
    return get_grid_config()

@router.post("/grid_config")
def api_update_grid_config(params: GridParams = Body(...)):
    update_grid_config(params.dict())
    return {"message": "Configuración actualizada", "config": get_grid_config()}

@router.get("/trades", response_model=List[dict])
def get_trades(
    symbol: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Trade)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    if side:
        query = query.filter(Trade.side == side.upper())
    trades = query.order_by(Trade.timestamp.desc()).all()
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "profit_loss": t.profit_loss,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None
        }
        for t in trades
    ]
