import logging
import time

# Filtro para evitar errores de símbolos inválidos
VALID_SYMBOLS = {
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SPKUSDT', 'ADAUSDT', 'SOLUSDT',
    'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LINKUSDT', 'UNIUSDT', 'ATOMUSDT'
}

def validate_symbol_before_query(symbol, logger):
    """Valida símbolo antes de consultar API"""
    if symbol not in VALID_SYMBOLS:
        logger.debug(f"Símbolo inválido filtrado: {symbol}")
        return False
    return True

def filter_symbol_errors(logger):
    """Filtra errores de símbolos inválidos repetitivos"""
    class SymbolErrorFilter(logging.Filter):
        def __init__(self):
            super().__init__()
            self.last_error = {}
            self.error_count = {}
        
        def filter(self, record):
            msg = record.getMessage()
            # Silenciar repetidos/rápidos para símbolos inválidos y mensajes de fallback
            if 'Invalid symbol' in msg or 'usando fallback' in msg:
                symbol = extract_symbol_from_error(record.getMessage())
                current_time = time.time()
                
                # Solo loggear si no se ha reportado en los últimos 60 segundos
                if symbol in self.last_error:
                    if current_time - self.last_error[symbol] < 60:
                        return False
                
                self.last_error[symbol] = current_time
                return True
            return True
    
    logger.addFilter(SymbolErrorFilter())

def extract_symbol_from_error(error_message):
    """Extrae símbolo de mensaje de error"""
    import re
    match = re.search(r'para ([A-Z]+USDT)', error_message)
    return match.group(1) if match else 'UNKNOWN'
