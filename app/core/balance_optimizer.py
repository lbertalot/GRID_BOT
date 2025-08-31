
"""
Optimizador de balance para 391.75 USDT
Maneja la distribución de capital y gestión de riesgo
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BalanceAllocation:
    """Asignación de balance por símbolo"""
    symbol: str
    allocated_amount: float
    max_orders: int
    current_balance: float = 0.0
    used_amount: float = 0.0

class BalanceOptimizer:
    """Optimizador de balance para trading seguro"""
    
    def __init__(self, total_balance: float = 391.75):
        self.total_balance = total_balance
        self.reserve_amount = 41.75  # 10.7% de reserva
        self.available_amount = total_balance - self.reserve_amount
        
        # Asignaciones por símbolo (en USDT)
        self.allocations = {
            "BTCUSDT": BalanceAllocation("BTCUSDT", 50.0, 3),
            "ETHUSDT": BalanceAllocation("ETHUSDT", 40.0, 3),
            "BNBUSDT": BalanceAllocation("BNBUSDT", 60.0, 4),
            "ADAUSDT": BalanceAllocation("ADAUSDT", 50.0, 4),
            "DOTUSDT": BalanceAllocation("DOTUSDT", 45.0, 4),
            "LINKUSDT": BalanceAllocation("LINKUSDT", 40.0, 3),
            "MATICUSDT": BalanceAllocation("MATICUSDT", 35.0, 4),
            "AVAXUSDT": BalanceAllocation("AVAXUSDT", 30.0, 3)
        }
        
        self.total_allocated = sum(alloc.allocated_amount for alloc in self.allocations.values())
        
        if self.total_allocated > self.available_amount:
            logger.warning(f"Total asignado ({self.total_allocated}) excede disponible ({self.available_amount})")
    
    def can_place_order(self, symbol: str, order_value: float) -> Tuple[bool, str]:
        """
        Verifica si se puede colocar una orden
        
        Args:
            symbol: Símbolo de trading
            order_value: Valor de la orden en USDT
            
        Returns:
            (puede_colocar, mensaje)
        """
        if symbol not in self.allocations:
            return False, f"Símbolo {symbol} no está en la configuración"
        
        allocation = self.allocations[symbol]
        
        # Verificar límite de asignación
        if allocation.used_amount + order_value > allocation.allocated_amount:
            return False, f"Orden excede asignación para {symbol}: ${allocation.allocated_amount}"
        
        # Verificar balance total disponible
        total_used = sum(alloc.used_amount for alloc in self.allocations.values())
        if total_used + order_value > self.available_amount:
            return False, f"Orden excede balance disponible: ${self.available_amount}"
        
        return True, "Orden válida"
    
    def record_order(self, symbol: str, order_value: float):
        """Registra una orden ejecutada"""
        if symbol in self.allocations:
            self.allocations[symbol].used_amount += order_value
            logger.info(f"Orden registrada: {symbol} - ${order_value:.2f}")
    
    def get_available_for_symbol(self, symbol: str) -> float:
        """Obtiene el monto disponible para un símbolo"""
        if symbol not in self.allocations:
            return 0.0
        
        allocation = self.allocations[symbol]
        return allocation.allocated_amount - allocation.used_amount
    
    def get_total_used(self) -> float:
        """Obtiene el total usado"""
        return sum(alloc.used_amount for alloc in self.allocations.values())
    
    def get_available_total(self) -> float:
        """Obtiene el total disponible"""
        return self.available_amount - self.get_total_used()
    
    def reset_daily_usage(self):
        """Resetea el uso diario (llamar al inicio del día)"""
        for allocation in self.allocations.values():
            allocation.used_amount = 0.0
        logger.info("Uso diario reseteado")
    
    def get_status_report(self) -> Dict:
        """Obtiene un reporte de estado"""
        return {
            "total_balance": self.total_balance,
            "reserve_amount": self.reserve_amount,
            "available_amount": self.available_amount,
            "total_used": self.get_total_used(),
            "total_available": self.get_available_total(),
            "allocations": {
                symbol: {
                    "allocated": alloc.allocated_amount,
                    "used": alloc.used_amount,
                    "available": alloc.allocated_amount - alloc.used_amount,
                    "max_orders": alloc.max_orders
                }
                for symbol, alloc in self.allocations.items()
            }
        }

# Instancia global
balance_optimizer = BalanceOptimizer()
