from app.services.binance_client import client
from sqlalchemy.orm import Session
from app.models.trade import Trade
from datetime import datetime
from typing import Optional

def get_binance_price(symbol: str):
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker["price"])

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
