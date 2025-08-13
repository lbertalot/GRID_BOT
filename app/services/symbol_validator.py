
# Filtro para símbolos válidos de Binance
VALID_SYMBOLS = {
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT',
    'AVAXUSDT', 'MATICUSDT', 'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT',
    'BCHUSDT', 'XLMUSDT', 'ALGOUSDT', 'VETUSDT', 'ICPUSDT', 'FILUSDT',
    'TRXUSDT', 'ETCUSDT', 'XMRUSDT', 'EOSUSDT', 'AAVEUSDT', 'CAKEUSDT',
    'MKRUSDT', 'COMPUSDT', 'SUSHIUSDT', 'CHZUSDT', 'HOTUSDT', 'DOGEUSDT',
    'SHIBUSDT', 'SPKUSDT'  # Agregar símbolos específicos del proyecto
}

def is_valid_symbol(symbol):
    """Verifica si un símbolo es válido"""
    return symbol in VALID_SYMBOLS

def filter_invalid_symbols(symbols):
    """Filtra símbolos inválidos de una lista"""
    return [symbol for symbol in symbols if is_valid_symbol(symbol)]

def log_symbol_validation(symbol, is_valid, logger):
    """Loggea validación de símbolos solo si es inválido"""
    if not is_valid:
        logger.warning(f"⚠️ Símbolo inválido detectado: {symbol}")
    return is_valid
