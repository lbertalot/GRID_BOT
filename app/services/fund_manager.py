"""
Servicio mejorado para la gestión de fondos y validaciones de trading
"""

import logging
import os
from typing import Dict, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from app.services.commission_manager import commission_manager
from app.services.binance_service import BinanceService

logger = logging.getLogger(__name__)

class FundManager:
    """
    Gestor de fondos mejorado con validaciones robustas
    """
    
    def __init__(self):
        load_dotenv()
        self.min_notional = float(os.getenv("MIN_NOTIONAL", "10.0"))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", "50.0"))
        self.safety_margin = float(os.getenv("SAFETY_MARGIN", "0.95"))  # 95% del balance disponible
        
    async def validate_trade_requirements(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        price: float,
        balances: Dict[str, float],
        order_type: str = 'MARKET'
    ) -> Tuple[bool, str, Dict]:
        """
        Valida si se pueden ejecutar los requisitos de trading considerando comisiones
        
        Args:
            symbol: Símbolo del par (ej: BTCUSDT)
            side: Lado de la operación (BUY/SELL)
            quantity: Cantidad a operar
            price: Precio actual
            balances: Balances disponibles
            order_type: Tipo de orden (MARKET/LIMIT)
            
        Returns:
            Tuple[bool, str, Dict]: (es_válido, mensaje, detalles)
        """
        try:
            # Extraer activos del símbolo
            base_asset = symbol.replace("USDT", "")
            quote_asset = "USDT"
            
            # Calcular valor nocional
            notional_value = quantity * price

            # Obtener filtros del símbolo (LOT_SIZE, MIN_NOTIONAL)
            effective_min_notional = self.min_notional
            min_qty_filter = None
            step_size = None
            try:
                symbol_info = BinanceService().get_symbol_info(symbol)
                if symbol_info:
                    step_size = float(symbol_info.get('stepSize', 0.0) or 0.0)
                    min_qty_filter = float(symbol_info.get('minQty', 0.0) or 0.0)
                    symbol_min_notional = float(symbol_info.get('minNotional', 0.0) or 0.0)
                    effective_min_notional = max(self.min_notional, symbol_min_notional)
            except Exception:
                pass

            # Ajustar cantidad a LOT_SIZE (step/minQty)
            def _round_down_to_step(q: float, step: float) -> float:
                if not step or step <= 0:
                    return q
                from math import floor, log10
                precision = int(max(0, round(-log10(step))))
                return float(f"{(floor(q / step) * step):.{precision}f}")

            adjusted_quantity = quantity
            if step_size:
                adjusted_quantity = _round_down_to_step(adjusted_quantity, step_size)
            if min_qty_filter and adjusted_quantity < min_qty_filter:
                adjusted_quantity = min_qty_filter
            notional_value = adjusted_quantity * price
            
            # Calcular comisión
            commission = commission_manager.calculate_commission(notional_value, order_type, symbol)
            
            # Validar valor mínimo
            if notional_value < effective_min_notional:
                # Calcular cantidad mínima requerida para cumplir min_notional del exchange
                min_quantity_required = effective_min_notional / price
                if step_size:
                    # elevar a múltiplo de step_size
                    from math import ceil
                    k = ceil(min_quantity_required / step_size)
                    min_quantity_required = k * step_size
                if min_qty_filter and min_quantity_required < min_qty_filter:
                    min_quantity_required = min_qty_filter

                required_notional = min_quantity_required * price
                required_commission = commission_manager.calculate_commission(required_notional, order_type, symbol)
                required_total_usdt = required_notional + required_commission
                return False, f"Valor nocional insuficiente: ${notional_value:.2f} < ${effective_min_notional}", {
                    "notional_value": notional_value,
                    "min_notional": effective_min_notional,
                    "required_increase": max(0.0, effective_min_notional - notional_value),
                    "min_quantity_required": min_quantity_required,
                    "required_total_usdt": required_total_usdt,
                    "quantity": min_quantity_required
                }
            
            # Validar tamaño máximo de posición
            if notional_value > self.max_position_size:
                return False, f"Tamaño de posición excede el máximo: ${notional_value:.2f} > ${self.max_position_size}", {
                    "notional_value": notional_value,
                    "max_position_size": self.max_position_size,
                    "excess": notional_value - self.max_position_size
                }
            
            if side == "BUY":
                # Para compras, necesitamos USDT (incluyendo comisión)
                usdt_balance = balances.get(quote_asset, 0)
                required_usdt = notional_value + commission  # Incluir comisión
                available_usdt = usdt_balance * self.safety_margin  # Aplicar margen de seguridad
                
                if required_usdt > available_usdt:
                    return False, f"Saldo USDT insuficiente para compra (incluyendo comisión): ${required_usdt:.2f} > ${available_usdt:.2f}", {
                        "required_usdt": required_usdt,
                        "available_usdt": available_usdt,
                        "usdt_balance": usdt_balance,
                        "commission_usdt": commission,
                        "safety_margin": self.safety_margin,
                        "shortage": required_usdt - available_usdt
                    }
                    
            elif side == "SELL":
                # Para ventas, necesitamos el activo base
                base_balance = balances.get(base_asset, 0)
                required_base = quantity
                available_base = base_balance * self.safety_margin  # Aplicar margen de seguridad
                
                if required_base > available_base:
                    return False, f"Saldo {base_asset} insuficiente para venta: {required_base} > {available_base}", {
                        "required_base": required_base,
                        "available_base": available_base,
                        "base_balance": base_balance,
                        "safety_margin": self.safety_margin,
                        "shortage": required_base - available_base
                    }
            
            # Todas las validaciones pasaron
            return True, "Validación exitosa", {
                "notional_value": notional_value,
                "commission_usdt": commission,
                "commission_percentage": (commission / notional_value * 100) if notional_value > 0 else 0,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "side": side,
                "quantity": adjusted_quantity,
                "price": price,
                "order_type": order_type
            }
            
        except Exception as e:
            logger.error(f"Error validando requisitos de trading: {e}")
            return False, f"Error en validación: {str(e)}", {}
    
    async def calculate_optimal_quantity(
        self, 
        symbol: str, 
        price: float, 
        balances: Dict[str, float],
        target_notional: Optional[float] = None
    ) -> Tuple[float, str, Dict]:
        """
        Calcula la cantidad óptima para operar
        
        Args:
            symbol: Símbolo del par
            price: Precio actual
            balances: Balances disponibles
            target_notional: Valor nocional objetivo (opcional)
            
        Returns:
            Tuple[float, str, Dict]: (cantidad_óptima, mensaje, detalles)
        """
        try:
            if target_notional is None:
                target_notional = self.min_notional
            
            # Calcular cantidad basada en valor nocional objetivo
            optimal_quantity = target_notional / price
            
            # Validar que la cantidad sea válida
            is_valid, message, details = await self.validate_trade_requirements(
                symbol, "BUY", optimal_quantity, price, balances
            )
            
            if not is_valid:
                # Intentar con cantidad mínima
                min_quantity = self.min_notional / price
                is_valid_min, message_min, details_min = await self.validate_trade_requirements(
                    symbol, "BUY", min_quantity, price, balances
                )
                
                if is_valid_min:
                    return min_quantity, f"Usando cantidad mínima: {message_min}", details_min
                else:
                    return 0.0, f"No se puede calcular cantidad válida: {message_min}", details_min
            
            return optimal_quantity, "Cantidad óptima calculada", details
            
        except Exception as e:
            logger.error(f"Error calculando cantidad óptima: {e}")
            return 0.0, f"Error en cálculo: {str(e)}", {}
    
    async def get_trading_summary(self, balances: Dict[str, float]) -> Dict:
        """
        Obtiene un resumen del estado de trading
        
        Args:
            balances: Balances disponibles
            
        Returns:
            Dict: Resumen del estado de trading
        """
        try:
            usdt_balance = balances.get("USDT", 0)
            btc_balance = balances.get("BTC", 0)
            eth_balance = balances.get("ETH", 0)
            spk_balance = balances.get("SPK", 0)
            
            # Calcular valores en USDT
            from app.services.binance_client_singleton import binance_client_singleton
            
            total_value = usdt_balance
            
            try:
                if btc_balance > 0:
                    btc_price = binance_client_singleton.get_symbol_price("BTCUSDT")
                    total_value += btc_balance * btc_price
            except:
                total_value += btc_balance * 114000  # Precio estimado
                
            try:
                if eth_balance > 0:
                    eth_price = binance_client_singleton.get_symbol_price("ETHUSDT")
                    total_value += eth_balance * eth_price
            except:
                total_value += eth_balance * 3500  # Precio estimado
                
            try:
                if spk_balance > 0:
                    spk_price = binance_client_singleton.get_symbol_price("SPKUSDT")
                    total_value += spk_balance * spk_price
            except:
                total_value += spk_balance * 0.1  # Precio estimado
            
            return {
                "total_value_usdt": round(total_value, 2),
                "usdt_balance": round(usdt_balance, 2),
                "btc_balance": btc_balance,
                "eth_balance": eth_balance,
                "spk_balance": spk_balance,
                "min_notional": self.min_notional,
                "max_position_size": self.max_position_size,
                "safety_margin": self.safety_margin,
                "can_trade": total_value >= self.min_notional,
                "max_trades_possible": int(usdt_balance * self.safety_margin / self.min_notional)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen de trading: {e}")
            return {
                "error": str(e),
                "can_trade": False
            }

# Instancia global
fund_manager = FundManager() 