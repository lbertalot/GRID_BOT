import os
import logging
import math

from apscheduler.schedulers.background import BackgroundScheduler
from binance import Client

from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.services.order_validation import OrderValidator
from app.services.telegram_alert import send_telegram_alert

# Configuración multi-activo final ajustada según requisitos Binance
multi_asset_grid_config = {
    'BNBUSDT': {
        'symbol': 'BNBUSDT',
        'min_price': 706.58,
        'max_price': 780.96,
        'grids': 8,
        'quantity': 0.007,  # Ajustado para cumplir mínimo notional $5
        'last_action': None,
        'is_active': True,
    },
    'ANIMEUSDT': {
        'symbol': 'ANIMEUSDT',
        'min_price': 0.018,
        'max_price': 0.02,
        'grids': 6,
        'quantity': 0.1,
        'last_action': None,
        'is_active': True,
    },
    'GPSUSDT': {
        'symbol': 'GPSUSDT',
        'min_price': 0.022,
        'max_price': 0.025,
        'grids': 6,
        'quantity': 0.1,
        'last_action': None,
        'is_active': True,
    },
    'GUNUSDT': {
        'symbol': 'GUNUSDT',
        'min_price': 0.034,
        'max_price': 0.037,
        'grids': 6,
        'quantity': 1.0,
        'last_action': None,
        'is_active': True,
    },
    'SIGNUSDT': {
        'symbol': 'SIGNUSDT',
        'min_price': 0.072,
        'max_price': 0.08,
        'grids': 6,
        'quantity': 1.0,
        'last_action': None,
        'is_active': True,
    },
    'SPKUSDT': {
        'symbol': 'SPKUSDT',
        'min_price': 0.036,
        'max_price': 0.04,
        'grids': 6,
        'quantity': 1.0,
        'last_action': None,
        'is_active': True,
    },
    'HOMEUSDT': {
        'symbol': 'HOMEUSDT',
        'min_price': 0.024,
        'max_price': 0.027,
        'grids': 6,
        'quantity': 1.0,
        'last_action': None,
        'is_active': True,
    },
    'HUMAUSDT': {
        'symbol': 'HUMAUSDT',
        'min_price': 0.034,
        'max_price': 0.038,
        'grids': 6,
        'quantity': 1.0,
        'last_action': None,
        'is_active': True,
    },
}

def adjust_quantity_precision(quantity: float, symbol: str = "BNBUSDT") -> float:
    """Ajusta la cantidad a la precisión requerida por Binance"""
    
    # Step sizes por símbolo (en producción se obtendrían de la API)
    step_sizes = {
        "BNBUSDT": 0.001,
        "ANIMEUSDT": 0.1,
        "GPSUSDT": 0.1,
        "GUNUSDT": 1.0,
        "SIGNUSDT": 1.0,
        "SPKUSDT": 1.0,
        "HOMEUSDT": 1.0,
        "HUMAUSDT": 1.0,
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

def execute_grid_trading_job():
    """Ejecuta execute_grid_trading_job."""
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_SECRET_KEY", "")
    client = Client(api_key, api_secret)
    
    # Crear validador de órdenes
    order_validator = OrderValidator(client)
    
    try:
        # Verificar balance antes de ejecutar
        account_info = client.get_account()
        balances = {b["asset"]: float(b["free"]) for b in account_info["balances"]}
        
        # Ejecutar grid trading para cada activo configurado
        for symbol, config in multi_asset_grid_config.items():
            if not config.get('is_active', True):
                continue
                
            try:
                # Obtener precio actual
                ticker = client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                
                # Calcular niveles de grid
                grid_levels = calculate_grid_levels(
                    config['min_price'],
                    config['max_price'],
                    config['grids']
                )
                
                # Decidir acción
                decision = decide_grid_action(
                    current_price,
                    grid_levels,
                    config.get('last_action', 'NONE')
                )
                
                if decision['action']:
                    # Ajustar cantidad a la precisión requerida
                    adjusted_quantity = adjust_quantity_precision(config['quantity'], symbol)
                    
                    # Verificar balance suficiente
                    base_asset = symbol.replace('USDT', '')
                    available_balance = balances.get(base_asset, 0)
                    
                    if decision['action'] == 'BUY':
                        # Para compras, verificar USDT disponible
                        usdt_needed = adjusted_quantity * current_price
                        if balances.get('USDT', 0) < usdt_needed:
                            logging.warning(f"USDT insuficiente para {symbol}: {usdt_needed} USDT necesarios")
                            continue
                    else:  # SELL
                        # Para ventas, verificar activo disponible
                        if available_balance < adjusted_quantity:
                            logging.warning(f"Balance insuficiente para {symbol}: {adjusted_quantity} {base_asset} necesarios")
                            continue
                    
                    # Ejecutar orden
                    result = order_validator.place_market_order_with_validation(
                        symbol, decision['action'], adjusted_quantity
                    )
                    
                    if result.get('success'):
                        # Actualizar última acción
                        config['last_action'] = decision['action']
                        
                        # Enviar notificación
                        order_info = result.get('order', {})
                        fills = order_info.get('fills', [])
                        
                        if fills:
                            executed_price = float(fills[0]['price'])
                            executed_qty = float(fills[0]['qty'])
                            
                            message = (
                                f"🤖 GridBot ejecutó {decision['action']} {executed_qty} {symbol} "
                                f"a ${executed_price:.6f}\n"
                                f"💰 Cantidad original: {adjusted_quantity}\n"
                                f"💸 Valor: ${executed_price * executed_qty:.2f}\n"
                                f"📋 Orden ID: {order_info.get('orderId', 'N/A')}"
                            )
                        else:
                            message = (
                                f"🤖 GridBot ejecutó {decision['action']} {adjusted_quantity} {symbol}\n"
                                f"📋 Orden ID: {order_info.get('orderId', 'N/A')}"
                            )
                        
                        send_telegram_alert(message)
                        logging.info(f"GridBot ejecutó {decision['action']} en {decision['price']}: {order_info}")
                    else:
                        logging.error(f"Error ejecutando orden para {symbol}: {result.get('error')}")
                        
            except Exception as e:
                logging.error(f"Error procesando {symbol}: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Error en grid job: {e}")

def update_grid_config(new_config: dict):
    """Actualizar configuración del grid"""
    global multi_asset_grid_config
    multi_asset_grid_config.update(new_config)

def get_grid_config() -> dict:
    """Obtener configuración actual del grid"""
    return multi_asset_grid_config

def start_scheduler():
    """Iniciar el scheduler de GridBot"""
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.add_job(execute_grid_trading_job, 'interval', seconds=60, id='grid_trading_job')
        scheduler.start()
        logging.info("Scheduler de GridBot multi-activo iniciado.") 