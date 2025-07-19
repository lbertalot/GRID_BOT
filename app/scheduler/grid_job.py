from apscheduler.schedulers.background import BackgroundScheduler
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from binance import Client
import os
import logging
from app.services.telegram_alert import send_telegram_alert

# Parámetros configurables (por defecto)
grid_config = {
    'symbol': 'BTCUSDT',
    'min_price': 20000,
    'max_price': 30000,
    'grids': 5,
    'quantity': 0.001,
    'last_action': None
}

scheduler = None

def run_grid_job():
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
    try:
        grid_levels = calculate_grid_levels(grid_config['min_price'], grid_config['max_price'], grid_config['grids'])
        ticker = client.get_symbol_ticker(symbol=grid_config['symbol'].upper())
        current_price = float(ticker["price"])
        decision = decide_grid_action(current_price, grid_levels, grid_config['last_action'])
        if decision["action"]:
            if decision["action"] == "BUY":
                result = client.order_market_buy(symbol=grid_config['symbol'].upper(), quantity=grid_config['quantity'])
            else:
                result = client.order_market_sell(symbol=grid_config['symbol'].upper(), quantity=grid_config['quantity'])
            logging.info(f"GridBot ejecutó {decision['action']} en {decision['level']}: {result}")
            send_telegram_alert(f"🤖 GridBot ejecutó {decision['action']} {grid_config['quantity']} {grid_config['symbol']} a {current_price}")
            grid_config['last_action'] = decision['action']
        else:
            logging.info(f"GridBot no ejecutó ninguna orden. Precio actual: {current_price}")
    except Exception as e:
        logging.error(f"Error en grid trading: {e}")
        send_telegram_alert(f"❌ Error en grid trading: {e}")

def update_grid_config(new_config: dict):
    global grid_config
    grid_config.update(new_config)
    logging.info(f"GridBot config actualizada: {grid_config}")

def get_grid_config() -> dict:
    return grid_config.copy()

def start_scheduler():
    global scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_grid_job, 'interval', seconds=60)
    scheduler.start()
    logging.info("Scheduler de GridBot iniciado.") 