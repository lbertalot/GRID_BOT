#!/usr/bin/env python3
"""
Script para aplicar la configuración optimizada para balance de 391.75 USDT
"""

import json
import shutil
import os
import sys
from datetime import datetime

def backup_current_config():
    """Hace backup de la configuración actual"""
    print("📦 Haciendo backup de la configuración actual...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"grid_config_backup_{timestamp}.json"
    
    if os.path.exists("grid_config_optimized.json"):
        shutil.copy("grid_config_optimized.json", backup_name)
        print(f"✅ Backup creado: {backup_name}")
        return backup_name
    else:
        print("⚠️ No se encontró configuración actual para hacer backup")
        return None

def apply_new_config():
    """Aplica la nueva configuración optimizada"""
    print("🔄 Aplicando nueva configuración optimizada...")
    
    # Copiar la nueva configuración
    shutil.copy("grid_config_optimized_391usdt.json", "grid_config_optimized.json")
    print("✅ Nueva configuración aplicada")

def validate_config():
    """Valida que la configuración sea correcta"""
    print("🔍 Validando configuración...")
    
    try:
        with open("grid_config_optimized.json", "r") as f:
            config = json.load(f)
        
        # Validar estructura
        required_keys = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "_optimization_metadata"]
        for key in required_keys:
            if key not in config:
                print(f"❌ Falta clave requerida: {key}")
                return False
        
        # Validar metadatos
        metadata = config["_optimization_metadata"]
        if metadata.get("total_balance") != 391.75:
            print("❌ Balance total incorrecto en metadatos")
            return False
        
        print("✅ Configuración válida")
        return True
        
    except Exception as e:
        print(f"❌ Error validando configuración: {e}")
        return False

def create_balance_optimizer():
    """Crea un optimizador de balance específico"""
    print("🎯 Creando optimizador de balance...")
    
    optimizer_code = '''
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
'''
    
    with open("app/core/balance_optimizer.py", "w") as f:
        f.write(optimizer_code)
    
    print("✅ Optimizador de balance creado")

def create_commission_aware_trading():
    """Crea trading consciente de comisiones"""
    print("💰 Creando trading consciente de comisiones...")
    
    commission_code = '''
"""
Trading consciente de comisiones para balance bajo
Asegura que las operaciones sean rentables después de comisiones
"""

import logging
from typing import Dict, Optional, Tuple
from app.services.commission import calculate_commission, validate_minimum_profit

logger = logging.getLogger(__name__)

class CommissionAwareTrading:
    """Trading que considera comisiones en todas las operaciones"""
    
    def __init__(self):
        self.min_profit_after_commission = 0.5  # 0.5%
        self.commission_rate = 0.001  # 0.1% por operación
    
    def validate_trade_profitability(
        self, 
        symbol: str, 
        buy_price: float, 
        sell_price: float, 
        quantity: float
    ) -> Tuple[bool, Dict]:
        """
        Valida si una operación será rentable después de comisiones
        
        Args:
            symbol: Símbolo de trading
            buy_price: Precio de compra
            sell_price: Precio de venta
            quantity: Cantidad
            
        Returns:
            (es_rentable, detalles)
        """
        try:
            # Calcular ganancia con comisiones
            is_profitable, profit_data = validate_minimum_profit(
                buy_price=buy_price,
                sell_price=sell_price,
                quantity=quantity,
                min_profit_percentage=self.min_profit_after_commission
            )
            
            if is_profitable:
                logger.info(f"✅ {symbol}: Operación rentable - Ganancia neta: ${profit_data['net_profit']:.4f}")
            else:
                logger.warning(f"⚠️ {symbol}: Operación no rentable - Pérdida neta: ${profit_data['net_profit']:.4f}")
            
            return is_profitable, profit_data
            
        except Exception as e:
            logger.error(f"Error validando rentabilidad de {symbol}: {e}")
            return False, {"error": str(e)}
    
    def calculate_optimal_quantity(
        self, 
        symbol: str, 
        available_usdt: float, 
        current_price: float,
        min_notional: float = 10.0
    ) -> Tuple[float, Dict]:
        """
        Calcula la cantidad óptima considerando comisiones
        
        Args:
            symbol: Símbolo de trading
            available_usdt: USDT disponible
            current_price: Precio actual
            min_notional: Valor mínimo requerido
            
        Returns:
            (cantidad_óptima, detalles)
        """
        try:
            # Calcular cantidad máxima posible
            max_quantity = available_usdt / current_price
            
            # Calcular comisión para esta cantidad
            notional_value = max_quantity * current_price
            commission = calculate_commission(notional_value, "MARKET", symbol)
            
            # Ajustar cantidad para incluir comisión
            adjusted_quantity = (available_usdt - commission.commission_usdt) / current_price
            
            # Verificar mínimo notional
            if adjusted_quantity * current_price < min_notional:
                # Calcular cantidad mínima que cumple notional + comisión
                min_quantity = min_notional / current_price
                commission_for_min = calculate_commission(min_notional, "MARKET", symbol)
                total_required = min_notional + commission_for_min.commission_usdt
                
                if total_required > available_usdt:
                    return 0.0, {
                        "error": f"Saldo insuficiente para cumplir mínimo notional + comisión",
                        "required": total_required,
                        "available": available_usdt
                    }
                
                adjusted_quantity = min_quantity
            
            return adjusted_quantity, {
                "original_quantity": max_quantity,
                "adjusted_quantity": adjusted_quantity,
                "commission": commission.commission_usdt,
                "notional_value": adjusted_quantity * current_price
            }
            
        except Exception as e:
            logger.error(f"Error calculando cantidad óptima para {symbol}: {e}")
            return 0.0, {"error": str(e)}
    
    def should_execute_trade(
        self, 
        symbol: str, 
        action: str, 
        price: float, 
        quantity: float,
        grid_level: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Decide si debe ejecutar una operación
        
        Args:
            symbol: Símbolo de trading
            action: BUY o SELL
            price: Precio de la operación
            quantity: Cantidad
            grid_level: Nivel de grid (opcional)
            
        Returns:
            (debe_ejecutar, razón)
        """
        try:
            # Para operaciones de grid, validar rentabilidad
            if grid_level is not None:
                # Simular precio de salida (nivel siguiente)
                if action == "BUY":
                    # Estimar precio de venta en el siguiente nivel
                    estimated_sell_price = price * 1.02  # 2% de ganancia estimada
                    is_profitable, _ = self.validate_trade_profitability(
                        symbol, price, estimated_sell_price, quantity
                    )
                    
                    if not is_profitable:
                        return False, f"Operación no rentable después de comisiones"
                
                elif action == "SELL":
                    # Para ventas, verificar que ya tengamos ganancia
                    # Esto se validaría con el precio de compra original
                    return True, "Venta de posición existente"
            
            # Para operaciones fuera de grid, ser más conservador
            else:
                if action == "BUY":
                    return False, "Operaciones fuera de grid deshabilitadas por seguridad"
            
            return True, "Operación válida"
            
        except Exception as e:
            logger.error(f"Error validando ejecución de {symbol}: {e}")
            return False, f"Error de validación: {e}"

# Instancia global
commission_aware_trading = CommissionAwareTrading()
'''
    
    with open("app/core/commission_aware_trading.py", "w") as f:
        f.write(commission_code)
    
    print("✅ Trading consciente de comisiones creado")

def update_trading_config():
    """Actualiza la configuración de trading"""
    print("⚙️ Actualizando configuración de trading...")
    
    config_updates = '''
# Configuración optimizada para balance de 391.75 USDT
TRADING_ENABLED=true
PAPER_TRADING=false
MIN_NOTIONAL=10.0
MAX_ACTIVE_ORDERS=20
DEFAULT_GRID_LEVELS=6

# Gestión de riesgo
MAX_DAILY_LOSS_PERCENT=2.0
MAX_POSITION_SIZE_PERCENT=15.0
STOP_LOSS_PERCENT=5.0
MAX_DRAWDOWN_PERCENT=10.0

# Comisiones
COMMISSION_AWARE=true
MIN_PROFIT_AFTER_COMMISSION=0.5

# Balance
TOTAL_BALANCE=391.75
RESERVE_AMOUNT=41.75
'''
    
    # Actualizar .env si existe
    if os.path.exists(".env"):
        with open(".env", "a") as f:
            f.write(f"\n# Configuración optimizada aplicada el {datetime.now()}\n")
            f.write(config_updates)
        print("✅ Configuración .env actualizada")
    
    print("✅ Configuración de trading actualizada")

def create_monitoring_script():
    """Crea script de monitoreo específico"""
    print("📊 Creando script de monitoreo...")
    
    monitoring_script = '''#!/usr/bin/env python3
"""
Script de monitoreo para balance de 391.75 USDT
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar el directorio app al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

async def monitor_391usdt_balance():
    """Monitorea el balance de 391.75 USDT"""
    try:
        from core.balance_optimizer import balance_optimizer
        from core.commission_aware_trading import commission_aware_trading
        
        print("💰 Monitoreo de Balance 391.75 USDT")
        print("=" * 50)
        
        # Obtener estado del optimizador
        status = balance_optimizer.get_status_report()
        
        print(f"📊 Estado del Balance:")
        print(f"   Balance total: ${status['total_balance']:.2f}")
        print(f"   Reserva: ${status['reserve_amount']:.2f}")
        print(f"   Disponible: ${status['available_amount']:.2f}")
        print(f"   Usado: ${status['total_used']:.2f}")
        print(f"   Libre: ${status['total_available']:.2f}")
        print()
        
        print("📈 Asignaciones por Símbolo:")
        for symbol, alloc in status['allocations'].items():
            print(f"   {symbol}:")
            print(f"     Asignado: ${alloc['allocated']:.2f}")
            print(f"     Usado: ${alloc['used']:.2f}")
            print(f"     Disponible: ${alloc['available']:.2f}")
            print(f"     Máx órdenes: {alloc['max_orders']}")
            print()
        
        # Verificar si hay problemas
        if status['total_used'] > status['available_amount'] * 0.9:
            print("⚠️ ADVERTENCIA: Uso de balance cercano al límite")
        
        if status['total_available'] < 20:
            print("⚠️ ADVERTENCIA: Balance disponible muy bajo")
        
        print("✅ Monitoreo completado")
        
    except Exception as e:
        print(f"❌ Error en monitoreo: {e}")

if __name__ == "__main__":
    asyncio.run(monitor_391usdt_balance())
'''
    
    with open("scripts/monitor_391usdt.py", "w") as f:
        f.write(monitoring_script)
    
    # Hacer el script ejecutable
    os.chmod("scripts/monitor_391usdt.py", 0o755)
    
    print("✅ Script de monitoreo creado")

def main():
    """Función principal"""
    print("🚀 Aplicando configuración optimizada para 391.75 USDT")
    print("=" * 60)
    
    try:
        # 1. Backup de configuración actual
        backup_file = backup_current_config()
        
        # 2. Aplicar nueva configuración
        apply_new_config()
        
        # 3. Validar configuración
        if not validate_config():
            print("❌ Error en validación de configuración")
            if backup_file:
                print(f"🔄 Restaurando configuración anterior: {backup_file}")
                shutil.copy(backup_file, "grid_config_optimized.json")
            return False
        
        # 4. Crear optimizador de balance
        create_balance_optimizer()
        
        # 5. Crear trading consciente de comisiones
        create_commission_aware_trading()
        
        # 6. Actualizar configuración
        update_trading_config()
        
        # 7. Crear script de monitoreo
        create_monitoring_script()
        
        print("\n✅ Configuración optimizada aplicada exitosamente!")
        print("\n📋 Resumen de cambios:")
        print("   🔄 Configuración de grid actualizada")
        print("   💰 Optimizador de balance creado")
        print("   🛡️ Trading consciente de comisiones")
        print("   📊 Script de monitoreo creado")
        print("   ⚙️ Configuración de trading actualizada")
        
        print("\n🎯 Próximos pasos:")
        print("   1. Reiniciar servicios: docker-compose restart")
        print("   2. Verificar funcionamiento: python3 scripts/monitor_391usdt.py")
        print("   3. Monitorear logs: tail -f logs/dockers.log")
        print("   4. Verificar operaciones en Binance")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error aplicando configuración: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
