from apscheduler.schedulers.background import BackgroundScheduler
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.services.order_validation import OrderValidator
from binance import Client
import os
import logging
import math
from app.services.telegram_alert import send_telegram_alert

# Parámetros configurables (por defecto)
grid_config = {
    'symbol': 'BNBUSDT',  # Cambiado a BNBUSDT para usar el balance disponible
    'min_price': 700,
    'max_price': 800,
    'grids': 8,
    'quantity': 0.002,  # Cantidad ajustada al balance disponible (0.00243376 BNB)
    'last_action': None
}

def adjust_quantity_precision(quantity: float, symbol: str = "BNBUSDT") -> float:
    """Ajusta la cantidad a la precisión requerida por Binance"""
    
    # Step sizes por símbolo (en producción se obtendrían de la API)
    step_sizes = {
        "BNBUSDT": 0.001,
        "BTCUSDT": 0.00001,
        "ETHUSDT": 0.001,
        "LTCUSDT": 0.01,
        "LINKUSDT": 0.01,
        "DOTUSDT": 0.01
    }
    
    step_size = step_sizes.get(symbol, 0.001)
    
    # Ajustar a la precisión requerida
    adjusted_quantity = math.floor(quantity / step_size) * step_size
    
    # Asegurar que no sea menor que el mínimo
    min_qty = step_size
    if adjusted_quantity < min_qty:
        adjusted_quantity = min_qty
    
    return round(adjusted_quantity, 6)  # Redondear a 6 decimales

scheduler = None

def run_grid_job():
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
    
    # Crear validador de órdenes
    order_validator = OrderValidator(client)
    
    try:
        # Verificar balance antes de ejecutar
        account_info = client.get_account()
        balances = {b["asset"]: float(b["free"]) for b in account_info["balances"]}
        
        symbol = grid_config['symbol']
        base_asset = symbol.replace("USDT", "")
        
        # Verificar si tenemos suficiente balance
        if base_asset in balances and balances[base_asset] >= grid_config['quantity']:
            grid_levels = calculate_grid_levels(grid_config['min_price'], grid_config['max_price'], grid_config['grids'])
            ticker = client.get_symbol_ticker(symbol=symbol.upper())
            current_price = float(ticker["price"])
            
            last_action = grid_config['last_action'] or "NONE"
            decision = decide_grid_action(current_price, grid_levels, last_action)
            
            if decision["action"]:
                action = decision["action"]
                quantity = grid_config['quantity']
                
                # Verificar balance específico para la acción
                if action == "BUY":
                    # Verificar USDT para compra
                    required_usdt = quantity * current_price
                    if balances.get('USDT', 0) >= required_usdt:
                        try:
                            result = order_validator.place_market_order_with_validation(symbol, action, quantity)
                            
                            # Enviar alerta de éxito con detalles
                            action_details = result['action_details']
                            success_msg = f"🤖 GridBot ejecutó {action_details['side']} {action_details['adjusted_quantity']} {action_details['symbol']} a ${action_details['current_price']:.2f}\n" \
                                         f"💰 Cantidad original: {action_details['original_quantity']}\n" \
                                         f"💸 Valor: ${action_details['notional_value']:.2f}\n" \
                                         f"📋 Orden ID: {result['order'].get('orderId', 'N/A')}"
                            send_telegram_alert(success_msg)
                            
                            grid_config['last_action'] = action
                            logging.info(f"GridBot ejecutó {action} en {decision['level']}: {result['order']}")
                            
                        except ValueError as ve:
                            # Error de validación o precisión
                            send_telegram_alert(str(ve))
                            logging.error(f"Error de validación en grid trading: {ve}")
                    else:
                        logging.warning(f"Balance USDT insuficiente para compra: {balances.get('USDT', 0)} < {required_usdt}")
                else:
                    # Verificar asset para venta
                    if balances.get(base_asset, 0) >= quantity:
                        try:
                            result = order_validator.place_market_order_with_validation(symbol, action, quantity)
                            
                            # Enviar alerta de éxito con detalles
                            action_details = result['action_details']
                            success_msg = f"🤖 GridBot ejecutó {action_details['side']} {action_details['adjusted_quantity']} {action_details['symbol']} a ${action_details['current_price']:.2f}\n" \
                                         f"💰 Cantidad original: {action_details['original_quantity']}\n" \
                                         f"💸 Valor: ${action_details['notional_value']:.2f}\n" \
                                         f"📋 Orden ID: {result['order'].get('orderId', 'N/A')}"
                            send_telegram_alert(success_msg)
                            
                            grid_config['last_action'] = action
                            logging.info(f"GridBot ejecutó {action} en {decision['level']}: {result['order']}")
                            
                        except ValueError as ve:
                            # Error de validación o precisión
                            send_telegram_alert(str(ve))
                            logging.error(f"Error de validación en grid trading: {ve}")
                    else:
                        logging.warning(f"Balance {base_asset} insuficiente para venta: {balances.get(base_asset, 0)} < {quantity}")
            else:
                logging.info(f"GridBot no ejecutó ninguna orden. Precio actual: ${current_price:.2f}")
        else:
            logging.warning(f"Balance insuficiente de {base_asset}: {balances.get(base_asset, 0)} < {grid_config['quantity']}")
            
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