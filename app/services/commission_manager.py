"""
Servicio para manejar comisiones de Binance de manera centralizada
"""

import logging
import os
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
from binance import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

class CommissionManager:
    """
    Gestor de comisiones de Binance que calcula y aplica comisiones
    en todas las operaciones de trading
    """
    
    def __init__(self):
        """Inicializar el gestor de comisiones"""
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        self.client = None
        self._commission_cache = {}
        self._symbol_info_cache = {}
        
        # Comisiones por defecto (se actualizarán desde Binance)
        self.default_maker_commission = 0.001  # 0.1%
        self.default_taker_commission = 0.001  # 0.1%
        
        # Inicializar cliente si hay credenciales
        if self.api_key and self.api_secret:
            try:
                self.client = Client(self.api_key, self.api_secret)
                self._update_commission_rates()
            except Exception as e:
                logger.warning(f"No se pudo inicializar cliente Binance para comisiones: {e}")
    
    def _update_commission_rates(self):
        """Actualizar tasas de comisión desde Binance"""
        try:
            if not self.client:
                return
                
            account_info = self.client.get_account()
            self.default_maker_commission = float(account_info.get('makerCommission', 15)) / 10000  # Convertir de puntos base
            self.default_taker_commission = float(account_info.get('takerCommission', 15)) / 10000
            
            logger.info(f"✅ Comisiones actualizadas - Maker: {self.default_maker_commission:.4f}, Taker: {self.default_taker_commission:.4f}")
            
        except Exception as e:
            logger.warning(f"No se pudieron actualizar comisiones: {e}")
    
    def get_commission_rates(self, symbol: str = None) -> Dict[str, float]:
        """
        Obtener tasas de comisión para un símbolo específico
        
        Args:
            symbol: Símbolo del par (ej: BTCUSDT)
            
        Returns:
            Dict con tasas de comisión maker y taker
        """
        if symbol and symbol in self._commission_cache:
            return self._commission_cache[symbol]
        
        # Por ahora usar comisiones por defecto
        # En el futuro se pueden obtener comisiones específicas por símbolo
        rates = {
            'maker': self.default_maker_commission,
            'taker': self.default_taker_commission
        }
        
        if symbol:
            self._commission_cache[symbol] = rates
            
        return rates
    
    def calculate_commission(self, notional_value: float, order_type: str = 'MARKET', symbol: str = None) -> float:
        """
        Calcular comisión para una operación
        
        Args:
            notional_value: Valor notional de la operación
            order_type: Tipo de orden (MARKET/LIMIT)
            symbol: Símbolo del par
            
        Returns:
            Comisión calculada en USDT
        """
        rates = self.get_commission_rates(symbol)
        
        # MARKET orders son taker, LIMIT orders son maker (generalmente)
        commission_rate = rates['taker'] if order_type == 'MARKET' else rates['maker']
        
        commission = notional_value * commission_rate
        
        # Redondear a 8 decimales para evitar errores de precisión
        return round(commission, 8)
    
    def calculate_net_quantity(self, gross_quantity: float, price: float, side: str, order_type: str = 'MARKET', symbol: str = None) -> float:
        """
        Calcular cantidad neta después de comisiones
        
        Args:
            gross_quantity: Cantidad bruta
            price: Precio por unidad
            side: Lado de la operación (BUY/SELL)
            order_type: Tipo de orden
            symbol: Símbolo del par
            
        Returns:
            Cantidad neta después de comisiones
        """
        notional_value = gross_quantity * price
        commission = self.calculate_commission(notional_value, order_type, symbol)
        
        if side == 'BUY':
            # Para compras, la comisión se paga en USDT, no afecta la cantidad recibida
            return gross_quantity
        else:  # SELL
            # Para ventas, la comisión se paga en el activo base
            commission_quantity = commission / price
            net_quantity = gross_quantity - commission_quantity
            return max(0, net_quantity)  # No puede ser negativo
    
    def calculate_required_quantity_for_target(self, target_quantity: float, price: float, side: str, order_type: str = 'MARKET', symbol: str = None) -> float:
        """
        Calcular cantidad requerida para obtener una cantidad objetivo después de comisiones
        
        Args:
            target_quantity: Cantidad objetivo después de comisiones
            price: Precio por unidad
            side: Lado de la operación (BUY/SELL)
            order_type: Tipo de orden
            symbol: Símbolo del par
            
        Returns:
            Cantidad requerida antes de comisiones
        """
        if side == 'BUY':
            # Para compras, la comisión no afecta la cantidad recibida
            return target_quantity
        else:  # SELL
            # Para ventas, calcular cantidad necesaria para obtener target_quantity después de comisiones
            rates = self.get_commission_rates(symbol)
            commission_rate = rates['taker'] if order_type == 'MARKET' else rates['maker']
            
            # Fórmula: target_quantity = gross_quantity * (1 - commission_rate)
            # Por lo tanto: gross_quantity = target_quantity / (1 - commission_rate)
            gross_quantity = target_quantity / (1 - commission_rate)
            return gross_quantity
    
    def calculate_profit_with_commissions(self, buy_price: float, sell_price: float, quantity: float, buy_order_type: str = 'MARKET', sell_order_type: str = 'MARKET', symbol: str = None) -> Dict[str, float]:
        """
        Calcular ganancia/pérdida considerando comisiones
        
        Args:
            buy_price: Precio de compra
            sell_price: Precio de venta
            quantity: Cantidad operada
            buy_order_type: Tipo de orden de compra
            sell_order_type: Tipo de orden de venta
            symbol: Símbolo del par
            
        Returns:
            Dict con ganancia bruta, comisiones totales y ganancia neta
        """
        # Calcular valores notionales
        buy_notional = quantity * buy_price
        sell_notional = quantity * sell_price
        
        # Calcular comisiones
        buy_commission = self.calculate_commission(buy_notional, buy_order_type, symbol)
        sell_commission = self.calculate_commission(sell_notional, sell_order_type, symbol)
        total_commission = buy_commission + sell_commission
        
        # Calcular ganancias
        gross_profit = sell_notional - buy_notional
        net_profit = gross_profit - total_commission
        
        return {
            'gross_profit': gross_profit,
            'buy_commission': buy_commission,
            'sell_commission': sell_commission,
            'total_commission': total_commission,
            'net_profit': net_profit,
            'profit_percentage': (net_profit / buy_notional * 100) if buy_notional > 0 else 0
        }
    
    def validate_minimum_profit(self, buy_price: float, sell_price: float, quantity: float, min_profit_percentage: float = 0.5, buy_order_type: str = 'MARKET', sell_order_type: str = 'MARKET', symbol: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Validar si una operación generará ganancia mínima después de comisiones
        
        Args:
            buy_price: Precio de compra
            sell_price: Precio de venta
            quantity: Cantidad operada
            min_profit_percentage: Porcentaje mínimo de ganancia requerido
            buy_order_type: Tipo de orden de compra
            sell_order_type: Tipo de orden de venta
            symbol: Símbolo del par
            
        Returns:
            Tuple[bool, Dict] - (es_rentable, detalles)
        """
        profit_data = self.calculate_profit_with_commissions(
            buy_price, sell_price, quantity, buy_order_type, sell_order_type, symbol
        )
        
        is_profitable = profit_data['profit_percentage'] >= min_profit_percentage
        
        return is_profitable, profit_data
    
    def adjust_grid_levels_for_commissions(self, min_price: float, max_price: float, num_levels: int, quantity: float, min_profit_percentage: float = 0.5, order_type: str = 'MARKET', symbol: str = None) -> Dict[str, Any]:
        """
        Ajustar niveles de grid para asegurar ganancia mínima después de comisiones
        
        Args:
            min_price: Precio mínimo del grid
            max_price: Precio máximo del grid
            num_levels: Número de niveles
            quantity: Cantidad por nivel
            min_profit_percentage: Porcentaje mínimo de ganancia
            order_type: Tipo de orden
            symbol: Símbolo del par
            
        Returns:
            Dict con niveles ajustados y análisis de rentabilidad
        """
        # Calcular espaciado original
        price_range = max_price - min_price
        original_spacing = price_range / (num_levels - 1)
        
        # Calcular comisión por operación
        avg_price = (min_price + max_price) / 2
        avg_notional = quantity * avg_price
        commission_per_trade = self.calculate_commission(avg_notional, order_type, symbol)
        
        # Calcular espaciado mínimo necesario para ganancia mínima
        min_spacing_percentage = min_profit_percentage / 100
        min_spacing = avg_price * min_spacing_percentage
        
        # Ajustar espaciado si es necesario
        adjusted_spacing = max(original_spacing, min_spacing)
        
        # Recalcular niveles con espaciado ajustado
        adjusted_levels = []
        for i in range(num_levels):
            level_price = min_price + (i * adjusted_spacing)
            if level_price <= max_price:
                adjusted_levels.append(level_price)
        
        # Analizar rentabilidad de cada nivel
        profitability_analysis = []
        for i in range(len(adjusted_levels) - 1):
            buy_price = adjusted_levels[i]
            sell_price = adjusted_levels[i + 1]
            
            is_profitable, profit_data = self.validate_minimum_profit(
                buy_price, sell_price, quantity, min_profit_percentage, order_type, order_type, symbol
            )
            
            profitability_analysis.append({
                'level': i + 1,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'is_profitable': is_profitable,
                'profit_percentage': profit_data['profit_percentage'],
                'net_profit': profit_data['net_profit']
            })
        
        return {
            'original_spacing': original_spacing,
            'adjusted_spacing': adjusted_spacing,
            'adjusted_levels': adjusted_levels,
            'profitability_analysis': profitability_analysis,
            'commission_per_trade': commission_per_trade,
            'min_profit_percentage': min_profit_percentage
        }

# Instancia global del gestor de comisiones
commission_manager = CommissionManager()
