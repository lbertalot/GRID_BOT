# Sistema de logging consolidado para trading
import logging
import json
from datetime import datetime
from typing import Dict, Any


class TradingLogger:
    """Logger consolidado para eventos de trading"""

    def __init__(self):
        self.logger = logging.getLogger("trading_system")
        self.cycle_summary = {}
        self.last_summary_time = None

    def log_trading_cycle(self, cycle_data: Dict[str, Any]):
        """Log consolidado de ciclo de trading"""
        current_time = datetime.now()

        # Solo loggear si hay cambios significativos o cada 5 minutos
        should_log = False
        if self.last_summary_time is None:
            should_log = True
        elif (current_time - self.last_summary_time).total_seconds() > 300:  # 5 minutos
            should_log = True
        elif cycle_data.get("trades_executed", 0) > 0:
            should_log = True

        if should_log:
            summary = {
                "timestamp": current_time.isoformat(),
                "total_trades": cycle_data.get("total_trades", 0),
                "trades_executed": cycle_data.get("trades_executed", 0),
                "success_rate": cycle_data.get("success_rate", 0.0),
                "mode": cycle_data.get("mode", "UNKNOWN"),
                "profit_loss": cycle_data.get("profit_loss", 0.0),
            }

            self.logger.info(f"📊 Resumen del ciclo de trading: {json.dumps(summary)}")
            self.last_summary_time = current_time
            self.cycle_summary = summary

    def log_balance_check(self, balances: Dict[str, float], has_issues: bool = False):
        """Log de verificación de balance"""
        if has_issues:
            self.logger.warning(
                f"⚠️ Problemas de balance detectados: {json.dumps(balances)}"
            )
        else:
            self.logger.debug(f"💰 Balance verificado: {json.dumps(balances)}")

    def log_order_execution(
        self, symbol: str, side: str, quantity: float, price: float, success: bool
    ):
        """Log de ejecución de orden"""
        order_data = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "total_value": quantity * price,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }

        if success:
            self.logger.info(f"✅ Orden ejecutada: {json.dumps(order_data)}")
        else:
            self.logger.error(f"❌ Orden fallida: {json.dumps(order_data)}")

    def log_profit_loss(self, symbol: str, profit_loss: float, roi: float):
        """Log de ganancias/pérdidas"""
        pl_data = {
            "symbol": symbol,
            "profit_loss": profit_loss,
            "roi": roi,
            "timestamp": datetime.now().isoformat(),
        }

        if profit_loss > 0:
            self.logger.info(f"📈 Ganancia: {json.dumps(pl_data)}")
        elif profit_loss < 0:
            self.logger.warning(f"📉 Pérdida: {json.dumps(pl_data)}")
        else:
            self.logger.debug(f"📊 Sin cambios: {json.dumps(pl_data)}")


# Instancia global
trading_logger = TradingLogger()
