#!/usr/bin/env python3
"""
Sistema de Paper Trading para GridBot V2.5
Permite probar el sistema sin riesgo real
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

class PaperTradingSystem:
    """
    Sistema de paper trading para simular operaciones
    """
    
    def __init__(self, initial_balance: float = 1000.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.positions = {}  # symbol -> {quantity, avg_price, unrealized_pnl}
        self.trade_history = []
        self.paper_trading_file = "paper_trading_state.json"
        self.load_state()
    
    def load_state(self):
        """Carga el estado del paper trading"""
        try:
            if os.path.exists(self.paper_trading_file):
                with open(self.paper_trading_file, 'r') as f:
                    data = json.load(f)
                    self.current_balance = data.get('current_balance', self.initial_balance)
                    self.positions = data.get('positions', {})
                    self.trade_history = data.get('trade_history', [])
                logger.info(f"✅ Estado de paper trading cargado: ${self.current_balance:.2f}")
        except Exception as e:
            logger.error(f"Error cargando estado de paper trading: {e}")
    
    def save_state(self):
        """Guarda el estado del paper trading"""
        try:
            data = {
                'current_balance': self.current_balance,
                'positions': self.positions,
                'trade_history': self.trade_history,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.paper_trading_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando estado de paper trading: {e}")
    
    def get_balance(self) -> float:
        """Obtiene el balance actual"""
        return self.current_balance
    
    def get_positions(self) -> Dict:
        """Obtiene las posiciones actuales"""
        return self.positions.copy()
    
    def get_trade_history(self) -> List[Dict]:
        """Obtiene el historial de trades"""
        return self.trade_history.copy()
    
    def place_buy_order(self, symbol: str, quantity: float, price: float) -> Dict:
        """
        Coloca una orden de compra
        
        Args:
            symbol: Símbolo del trading pair
            quantity: Cantidad a comprar
            price: Precio de compra
            
        Returns:
            Dict: Resultado de la orden
        """
        try:
            # Calcular costo total
            total_cost = quantity * price
            
            # Verificar balance suficiente
            if total_cost > self.current_balance:
                return {
                    'success': False,
                    'error': f'Balance insuficiente: ${total_cost:.2f} > ${self.current_balance:.2f}',
                    'order_id': None
                }
            
            # Ejecutar orden
            self.current_balance -= total_cost
            
            # Actualizar posiciones
            if symbol in self.positions:
                # Posición existente
                pos = self.positions[symbol]
                total_quantity = pos['quantity'] + quantity
                total_value = (pos['quantity'] * pos['avg_price']) + total_cost
                pos['avg_price'] = total_value / total_quantity
                pos['quantity'] = total_quantity
            else:
                # Nueva posición
                self.positions[symbol] = {
                    'quantity': quantity,
                    'avg_price': price,
                    'unrealized_pnl': 0.0
                }
            
            # Registrar trade
            trade = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'side': 'BUY',
                'quantity': quantity,
                'price': price,
                'total_cost': total_cost,
                'balance_after': self.current_balance
            }
            self.trade_history.append(trade)
            
            self.save_state()
            
            logger.info(f"📈 Paper trading BUY: {symbol} {quantity} @ ${price:.2f} = ${total_cost:.2f}")
            
            return {
                'success': True,
                'order_id': f"paper_buy_{len(self.trade_history)}",
                'executed_quantity': quantity,
                'executed_price': price,
                'total_cost': total_cost,
                'balance_after': self.current_balance
            }
            
        except Exception as e:
            logger.error(f"Error en orden de compra paper trading: {e}")
            return {
                'success': False,
                'error': str(e),
                'order_id': None
            }
    
    def place_sell_order(self, symbol: str, quantity: float, price: float) -> Dict:
        """
        Coloca una orden de venta
        
        Args:
            symbol: Símbolo del trading pair
            quantity: Cantidad a vender
            price: Precio de venta
            
        Returns:
            Dict: Resultado de la orden
        """
        try:
            # Verificar posición existente
            if symbol not in self.positions:
                return {
                    'success': False,
                    'error': f'No hay posición en {symbol}',
                    'order_id': None
                }
            
            position = self.positions[symbol]
            if position['quantity'] < quantity:
                return {
                    'success': False,
                    'error': f'Cantidad insuficiente: {quantity} > {position["quantity"]}',
                    'order_id': None
                }
            
            # Calcular ganancia/pérdida
            total_revenue = quantity * price
            total_cost = quantity * position['avg_price']
            realized_pnl = total_revenue - total_cost
            
            # Ejecutar orden
            self.current_balance += total_revenue
            
            # Actualizar posición
            position['quantity'] -= quantity
            if position['quantity'] <= 0:
                # Posición cerrada
                del self.positions[symbol]
            else:
                # Actualizar precio promedio
                remaining_cost = position['quantity'] * position['avg_price']
                position['avg_price'] = remaining_cost / position['quantity']
            
            # Registrar trade
            trade = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'side': 'SELL',
                'quantity': quantity,
                'price': price,
                'total_revenue': total_revenue,
                'realized_pnl': realized_pnl,
                'balance_after': self.current_balance
            }
            self.trade_history.append(trade)
            
            self.save_state()
            
            logger.info(f"📉 Paper trading SELL: {symbol} {quantity} @ ${price:.2f} = ${total_revenue:.2f} (PnL: ${realized_pnl:.2f})")
            
            return {
                'success': True,
                'order_id': f"paper_sell_{len(self.trade_history)}",
                'executed_quantity': quantity,
                'executed_price': price,
                'total_revenue': total_revenue,
                'realized_pnl': realized_pnl,
                'balance_after': self.current_balance
            }
            
        except Exception as e:
            logger.error(f"Error en orden de venta paper trading: {e}")
            return {
                'success': False,
                'error': str(e),
                'order_id': None
            }
    
    def update_positions_pnl(self, current_prices: Dict[str, float]):
        """
        Actualiza el PnL no realizado de las posiciones
        
        Args:
            current_prices: Diccionario de precios actuales por símbolo
        """
        total_unrealized_pnl = 0.0
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                market_value = position['quantity'] * current_price
                cost_basis = position['quantity'] * position['avg_price']
                unrealized_pnl = market_value - cost_basis
                
                position['unrealized_pnl'] = unrealized_pnl
                total_unrealized_pnl += unrealized_pnl
        
        return total_unrealized_pnl
    
    def get_portfolio_summary(self, current_prices: Dict[str, float] = None) -> Dict:
        """
        Obtiene un resumen del portafolio
        
        Args:
            current_prices: Precios actuales para calcular PnL no realizado
            
        Returns:
            Dict: Resumen del portafolio
        """
        total_unrealized_pnl = 0.0
        positions_summary = []
        
        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, position['avg_price']) if current_prices else position['avg_price']
            market_value = position['quantity'] * current_price
            cost_basis = position['quantity'] * position['avg_price']
            unrealized_pnl = market_value - cost_basis
            
            positions_summary.append({
                'symbol': symbol,
                'quantity': position['quantity'],
                'avg_price': position['avg_price'],
                'current_price': current_price,
                'market_value': market_value,
                'cost_basis': cost_basis,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
            })
            
            total_unrealized_pnl += unrealized_pnl
        
        # Calcular PnL total realizado
        total_realized_pnl = sum(trade.get('realized_pnl', 0) for trade in self.trade_history)
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.current_balance,
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_realized_pnl': total_realized_pnl,
            'total_pnl': total_unrealized_pnl + total_realized_pnl,
            'total_pnl_pct': ((total_unrealized_pnl + total_realized_pnl) / self.initial_balance * 100),
            'positions': positions_summary,
            'total_trades': len(self.trade_history),
            'open_positions': len(self.positions)
        }
    
    def reset_paper_trading(self, new_balance: float = None):
        """
        Resetea el paper trading
        
        Args:
            new_balance: Nuevo balance inicial (opcional)
        """
        if new_balance:
            self.initial_balance = new_balance
        
        self.current_balance = self.initial_balance
        self.positions = {}
        self.trade_history = []
        
        self.save_state()
        
        logger.info(f"🔄 Paper trading reseteado con balance: ${self.initial_balance:.2f}")

# Instancia global del sistema de paper trading
paper_trading_system = PaperTradingSystem()

def get_paper_trading() -> PaperTradingSystem:
    """Función de conveniencia para obtener el sistema de paper trading"""
    return paper_trading_system

def place_paper_buy_order(symbol: str, quantity: float, price: float) -> Dict:
    """Función de conveniencia para orden de compra"""
    return paper_trading_system.place_buy_order(symbol, quantity, price)

def place_paper_sell_order(symbol: str, quantity: float, price: float) -> Dict:
    """Función de conveniencia para orden de venta"""
    return paper_trading_system.place_sell_order(symbol, quantity, price)

def get_paper_portfolio_summary(current_prices: Dict[str, float] = None) -> Dict:
    """Función de conveniencia para obtener resumen del portafolio"""
    return paper_trading_system.get_portfolio_summary(current_prices)
