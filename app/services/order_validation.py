import math
import logging
from typing import Dict, Any, Optional, Tuple

from binance import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

class OrderValidator:
    """Clase para validar y ajustar parámetros de órdenes de trading"""
    
    def __init__(self, client: Client):
        """Ejecuta __init__."""
        self.client = client
        self._symbol_info_cache = {}
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de un símbolo incluyendo stepSize y minQty"""
        try:
            if symbol not in self._symbol_info_cache:
                exchange_info = self.client.get_exchange_info()
                for s in exchange_info['symbols']:
                    if s['symbol'] == symbol.upper():
                        # Extraer filtros importantes
                        filters = {f['filterType']: f for f in s['filters']}
                        self._symbol_info_cache[symbol] = {
                            'symbol': s['symbol'],
                            'baseAsset': s['baseAsset'],
                            'quoteAsset': s['quoteAsset'],
                            'stepSize': float(filters.get('LOT_SIZE', {}).get('stepSize', '0.001')),
                            'minQty': float(filters.get('LOT_SIZE', {}).get('minQty', '0.001')),
                            'maxQty': float(filters.get('LOT_SIZE', {}).get('maxQty', '1000000.0')),
                            'minNotional': float(filters.get('MIN_NOTIONAL', {}).get('minNotional', '5.0')),
                            'tickSize': float(filters.get('PRICE_FILTER', {}).get('tickSize', '0.01')),
                            'minPrice': float(filters.get('PRICE_FILTER', {}).get('minPrice', '0.0')),
                            'maxPrice': float(filters.get('PRICE_FILTER', {}).get('maxPrice', '0.0')),
                            'pricePrecision': s['quotePrecision'],
                            'quantityPrecision': s['baseAssetPrecision']
                        }
                        break
            return self._symbol_info_cache.get(symbol)
        except Exception as e:
            logger.error(f"Error obteniendo información del símbolo {symbol}: {e}")
            return None
    
    def _round_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step

    def _round_to_tick(self, price: float, tick: float) -> float:
        if tick <= 0:
            return price
        return math.floor(price / tick) * tick

    def adjust_quantity_precision(self, quantity: float, symbol: str) -> Dict[str, Any]:
        """Ajusta la cantidad a la precisión requerida por Binance y retorna información detallada"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                # Fallback a valores por defecto
                step_size = 0.001
                min_qty = 0.001
                max_qty = 1000000.0
                min_notional = 5.0
            else:
                step_size = symbol_info['stepSize']
                min_qty = symbol_info['minQty']
                max_qty = symbol_info.get('maxQty', 1000000.0)
                min_notional = symbol_info['minNotional']
            
            # Ajustar a la precisión requerida
            adjusted_quantity = self._round_to_step(quantity, step_size)
            
            # Asegurar que no sea menor que el mínimo
            if adjusted_quantity < min_qty:
                adjusted_quantity = min_qty
            # Limitar al máximo si aplica
            if adjusted_quantity > max_qty:
                adjusted_quantity = max_qty
            
            # Redondear a la precisión correcta
            precision = int(-math.log10(step_size))
            adjusted_quantity = round(adjusted_quantity, precision)
            
            return {
                'original_quantity': quantity,
                'adjusted_quantity': adjusted_quantity,
                'step_size': step_size,
                'min_qty': min_qty,
                'max_qty': max_qty,
                'min_notional': min_notional,
                'precision': precision,
                'symbol_info': symbol_info
            }
        except Exception as e:
            logger.error(f"Error ajustando precisión de cantidad: {e}")
            return {
                'original_quantity': quantity,
                'adjusted_quantity': quantity,
                'step_size': 0.001,
                'min_qty': 0.001,
                'max_qty': 1000000.0,
                'min_notional': 5.0,
                'precision': 3,
                'symbol_info': None,
                'error': str(e)
            }
    
    def validate_order_parameters(self, symbol: str, quantity: float, side: str, order_type: str = 'MARKET', price: Optional[float] = None) -> Dict[str, Any]:
        """Valida los parámetros de una orden antes de ejecutarla.
        - Ajusta cantidad a `stepSize`
        - Ajusta precio (si LIMIT) a `tickSize` y valida rangos de precio
        - Valida `minQty`/`maxQty` y `minNotional`
        """
        try:
            # Ajustar cantidad
            quantity_info = self.adjust_quantity_precision(quantity, symbol)
            
            # Obtener precio actual para validaciones
            ticker = self.client.get_symbol_ticker(symbol=symbol.upper())
            current_price = float(ticker["price"])

            # Calcular precio considerado para notional/validación
            symbol_info = quantity_info['symbol_info'] or {}
            tick_size = float(symbol_info.get('tickSize', 0.01) or 0.01)
            min_price = float(symbol_info.get('minPrice', 0.0) or 0.0)
            max_price = float(symbol_info.get('maxPrice', 0.0) or 0.0)

            adjusted_price = None
            if order_type.upper() == 'LIMIT':
                if price is None:
                    raise ValueError("Precio requerido para órdenes LIMIT")
                adjusted_price = self._round_to_tick(price, tick_size)
                # Validar rango de precio si min/max definidos
                if min_price > 0 and adjusted_price < min_price:
                    raise ValueError(f"Precio {adjusted_price} es menor que el mínimo permitido {min_price}")
                if max_price > 0 and adjusted_price > max_price:
                    raise ValueError(f"Precio {adjusted_price} es mayor que el máximo permitido {max_price}")
            else:
                adjusted_price = current_price
            
            # Calcular valor notional
            notional_value = quantity_info['adjusted_quantity'] * adjusted_price
            
            # Validaciones
            errors = []
            warnings = []
            
            if quantity_info['adjusted_quantity'] < quantity_info['min_qty']:
                errors.append(f"Cantidad {quantity_info['adjusted_quantity']} es menor al mínimo {quantity_info['min_qty']}")
            if quantity_info['adjusted_quantity'] > quantity_info['max_qty']:
                errors.append(f"Cantidad {quantity_info['adjusted_quantity']} supera el máximo {quantity_info['max_qty']}")
            
            if notional_value < quantity_info['min_notional']:
                errors.append(f"Valor notional ${notional_value:.2f} es menor al mínimo ${quantity_info['min_notional']}")
            
            if quantity_info['original_quantity'] != quantity_info['adjusted_quantity']:
                warnings.append(f"Cantidad ajustada de {quantity_info['original_quantity']} a {quantity_info['adjusted_quantity']} por precisión")
            if order_type.upper() == 'LIMIT' and adjusted_price != price:
                warnings.append(f"Precio ajustado de {price} a {adjusted_price} por tickSize {tick_size}")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'quantity_info': quantity_info,
                'current_price': current_price,
                'adjusted_price': adjusted_price,
                'notional_value': notional_value,
                'recommended_quantity': quantity_info['adjusted_quantity']
            }
        except Exception as e:
            logger.error(f"Error validando parámetros de orden: {e}")
            return {
                'is_valid': False,
                'errors': [f"Error en validación: {e}"],
                'warnings': [],
                'quantity_info': None,
                'current_price': None,
                'adjusted_price': None,
                'notional_value': None,
                'recommended_quantity': None
            }
    
    def place_market_order_with_validation(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """Coloca una orden de mercado con validación previa completa"""
        try:
            # Validar parámetros
            validation = self.validate_order_parameters(symbol, quantity, side, 'MARKET')
            
            if not validation['is_valid']:
                error_msg = f"❌ Parámetros de orden inválidos para {side} {quantity} {symbol}\n"
                for error in validation['errors']:
                    error_msg += f"🔴 {error}\n"
                if validation['warnings']:
                    error_msg += "\n⚠️ Advertencias:\n"
                    for warning in validation['warnings']:
                        error_msg += f"🟡 {warning}\n"
                error_msg += f"💡 Cantidad recomendada: {validation['recommended_quantity']}"
                raise ValueError(error_msg)
            
            # Usar cantidad ajustada
            adjusted_quantity = validation['quantity_info']['adjusted_quantity']
            
            # Ejecutar orden
            if side.upper() == 'BUY':
                result = self.client.order_market_buy(symbol=symbol.upper(), quantity=adjusted_quantity)
            elif side.upper() == 'SELL':
                result = self.client.order_market_sell(symbol=symbol.upper(), quantity=adjusted_quantity)
            else:
                raise ValueError(f"Lado de orden inválido: {side}")
            
            return {
                'order': result,
                'validation': validation,
                'executed_quantity': adjusted_quantity,
                'action_details': {
                    'symbol': symbol.upper(),
                    'side': side.upper(),
                    'original_quantity': quantity,
                    'adjusted_quantity': adjusted_quantity,
                    'current_price': validation['current_price'],
                    'notional_value': validation['notional_value']
                }
            }
            
        except BinanceAPIException as e:
            # Manejo específico de errores de Binance
            error_details = self._format_binance_error(e, symbol, side, quantity)
            raise ValueError(error_details)
        except Exception as e:
            logger.error(f"Error colocando orden de mercado: {e}")
            raise
    
    def _format_binance_error(self, e: BinanceAPIException, symbol: str, side: str, quantity: float) -> str:
        """Formatea errores de Binance con información detallada"""
        error_code = getattr(e, 'code', 'N/A')
        error_message = getattr(e, 'message', str(e))
        
        # Errores específicos de precisión
        if error_code == -1111:
            # Obtener información del símbolo para sugerir cantidad correcta
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                step_size = symbol_info['stepSize']
                min_qty = symbol_info['minQty']
                recommended_qty = math.floor(quantity / step_size) * step_size
                if recommended_qty < min_qty:
                    recommended_qty = min_qty
                
                error_msg = f"❌ Error de Precisión en Cantidad\n" \
                           f"📊 Símbolo: {symbol.upper()}\n" \
                           f"🔄 Acción: {side.upper()}\n" \
                           f"💰 Cantidad original: {quantity}\n" \
                           f"🔢 Step Size: {step_size}\n" \
                           f"📏 Cantidad mínima: {min_qty}\n" \
                           f"💡 Cantidad recomendada: {recommended_qty}\n" \
                           f"🔍 Código de error: {error_code}\n" \
                           f"📝 Mensaje: {error_message}"
            else:
                error_msg = f"❌ Error de Precisión en Cantidad\n" \
                           f"📊 Símbolo: {symbol.upper()}\n" \
                           f"🔄 Acción: {side.upper()}\n" \
                           f"💰 Cantidad: {quantity}\n" \
                           f"🔍 Código de error: {error_code}\n" \
                           f"📝 Mensaje: {error_message}\n" \
                           f"💡 Sugerencia: Reducir la cantidad o verificar la precisión del símbolo"
        
        elif error_code == -2010:
            error_msg = f"❌ Balance Insuficiente\n" \
                       f"📊 Símbolo: {symbol.upper()}\n" \
                       f"🔄 Acción: {side.upper()}\n" \
                       f"💰 Cantidad: {quantity}\n" \
                       f"🔍 Código de error: {error_code}\n" \
                       f"📝 Mensaje: {error_message}"
        
        elif error_code == -2011:
            error_msg = f"❌ Error de Precio\n" \
                       f"📊 Símbolo: {symbol.upper()}\n" \
                       f"🔄 Acción: {side.upper()}\n" \
                       f"💰 Cantidad: {quantity}\n" \
                       f"🔍 Código de error: {error_code}\n" \
                       f"📝 Mensaje: {error_message}"
        
        else:
            error_msg = f"❌ Error de Binance API\n" \
                       f"📊 Símbolo: {symbol.upper()}\n" \
                       f"🔄 Acción: {side.upper()}\n" \
                       f"💰 Cantidad: {quantity}\n" \
                       f"🔍 Código de error: {error_code}\n" \
                       f"📝 Mensaje: {error_message}"
        
        return error_msg 