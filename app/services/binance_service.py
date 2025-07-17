from app.services.binance_client import client

def get_binance_price(symbol: str):
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker["price"])
