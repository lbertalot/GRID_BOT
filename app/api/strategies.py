from fastapi import APIRouter, Body, HTTPException, Query
from typing import Literal
from app.services.strategies.trailing_stop import trailing_stop_strategy
from app.services.strategies.scalping import scalping_strategy
from app.services.strategies.rsi_macd import rsi_macd_strategy
from binance import Client
import os

router = APIRouter()


def get_price_history(symbol: str, interval: str, limit: int) -> list[float]:
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_SECRET_KEY", "")
    client = Client(api_key, api_secret)
    klines = client.get_klines(symbol=symbol.upper(), interval=interval, limit=limit)
    return [float(k[4]) for k in klines]


@router.post("/strategy/trailing_stop")
def run_trailing_stop(
    symbol: str = Body("BTCUSDT"),
    interval: str = Body("1h"),
    limit: int = Body(50),
    price_history: list[float] = Body(default=None),
    balances: dict = Body(...),
    params: dict = Body(default={}),
):
    if price_history is None:
        try:
            price_history = get_price_history(symbol, interval, limit)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Error obteniendo histórico de Binance: {e}"
            )
    result = trailing_stop_strategy(
        price_history=price_history, balances=balances, params=params
    )
    return result


@router.post("/strategy/scalping")
def run_scalping(
    symbol: str = Body("BTCUSDT"),
    interval: str = Body("1m"),
    limit: int = Body(10),
    price_history: list[float] = Body(default=None),
    balances: dict = Body(...),
    params: dict = Body(default={}),
):
    if price_history is None:
        try:
            price_history = get_price_history(symbol, interval, limit)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Error obteniendo histórico de Binance: {e}"
            )
    result = scalping_strategy(
        price_history=price_history, balances=balances, params=params
    )
    return result


@router.post("/strategy/rsi_macd")
def run_rsi_macd(
    symbol: str = Body("BTCUSDT"),
    interval: str = Body("1h"),
    limit: int = Body(50),
    price_history: list[float] = Body(default=None),
    balances: dict = Body(...),
    params: dict = Body(default={}),
):
    if price_history is None:
        try:
            price_history = get_price_history(symbol, interval, limit)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Error obteniendo histórico de Binance: {e}"
            )
    result = rsi_macd_strategy(
        price_history=price_history, balances=balances, params=params
    )
    return result


strategy_map = {
    "trailing_stop": trailing_stop_strategy,
    "scalping": scalping_strategy,
    "rsi_macd": rsi_macd_strategy,
}


@router.post("/strategy/backtest")
def backtest_strategy(
    strategy: Literal["trailing_stop", "scalping", "rsi_macd"] = Query(...),
    symbol: str = Body("BTCUSDT"),
    interval: str = Body("1h"),
    limit: int = Body(50),
    balances: dict = Body(...),
    params: dict = Body(default={}),
):
    try:
        price_history = get_price_history(symbol, interval, limit)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error obteniendo histórico de Binance: {e}"
        )
    strat_fn = strategy_map[strategy]
    # Simulación simple: ejecuta la estrategia en cada punto del histórico
    results = []
    for i in range(10, len(price_history)):
        sub_history = price_history[: i + 1]
        result = strat_fn(price_history=sub_history, balances=balances, params=params)
        results.append({"step": i, "price": price_history[i], **result})
    return results
