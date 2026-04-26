"""
Strategy Blacklist - Sistema de desactivación de estrategias fallidas
GridBot v2.5 - Protección contra estrategias que causan pérdidas masivas
"""

import logging
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.trade import Trade

logger = logging.getLogger(__name__)


class StrategyBlacklist:
    """
    Sistema de blacklist para desactivar estrategias y símbolos que causan pérdidas masivas
    """

    def __init__(self, config_file: str = "strategy_blacklist.json"):
        self.config_file = config_file
        self.logger = logger

        # Blacklist por defecto basada en análisis de pérdidas
        self.default_blacklist = {
            "symbols": {
                "SPKUSDT": {
                    "reason": "Pérdida masiva: -653.96 USDT (57% del total)",
                    "added_date": datetime.now().isoformat(),
                    "loss_amount": -653.96,
                    "loss_percentage": 0.57,
                },
                "BTCUSDT": {
                    "reason": "Pérdida alta: -240.34 USDT",
                    "added_date": datetime.now().isoformat(),
                    "loss_amount": -240.34,
                    "loss_percentage": 0.21,
                },
                "AVAXUSDT": {
                    "reason": "Pérdida crítica: -145.39 USDT",
                    "added_date": datetime.now().isoformat(),
                    "loss_amount": -145.39,
                    "loss_percentage": 0.13,
                },
                "BNBUSDT": {
                    "reason": "Pérdida alta: -74.92 USDT",
                    "added_date": datetime.now().isoformat(),
                    "loss_amount": -74.92,
                    "loss_percentage": 0.07,
                },
                "LINKUSDT": {
                    "reason": "Pérdida alta: -58.55 USDT",
                    "added_date": datetime.now().isoformat(),
                    "loss_amount": -58.55,
                    "loss_percentage": 0.05,
                },
            },
            "strategies": {
                "GridTrading": {
                    "symbols": [
                        "SPKUSDT",
                        "BTCUSDT",
                        "AVAXUSDT",
                        "BNBUSDT",
                        "LINKUSDT",
                    ],
                    "reason": "Estrategia GridTrading fallida en múltiples símbolos",
                    "added_date": datetime.now().isoformat(),
                }
            },
            "auto_blacklist_thresholds": {
                "max_loss_per_symbol": -100.0,  # -100 USDT máximo por símbolo
                "max_loss_percentage": 0.20,  # 20% pérdida máxima por símbolo
                "max_consecutive_losses": 10,  # 10 pérdidas consecutivas máximo
                "min_trades_for_analysis": 50,  # Mínimo 50 trades para análisis
            },
        }

        # Cargar blacklist desde archivo o usar por defecto
        self.blacklist = self._load_blacklist()

        self.logger.info(
            f"🚫 Strategy Blacklist inicializado con {len(self.blacklist['symbols'])} símbolos bloqueados"
        )

    def _load_blacklist(self) -> Dict:
        """Cargar blacklist desde archivo o usar por defecto"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    return json.load(f)
            else:
                # Crear archivo con blacklist por defecto
                self._save_blacklist(self.default_blacklist)
                return self.default_blacklist
        except Exception as e:
            self.logger.error(f"Error cargando blacklist: {e}")
            return self.default_blacklist

    def _save_blacklist(self, blacklist: Dict):
        """Guardar blacklist en archivo"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(blacklist, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando blacklist: {e}")

    def is_symbol_blacklisted(self, symbol: str) -> bool:
        """Verificar si un símbolo está en la blacklist"""
        return symbol in self.blacklist["symbols"]

    def is_strategy_blacklisted(self, strategy: str, symbol: str = None) -> bool:
        """Verificar si una estrategia está en la blacklist"""
        if strategy not in self.blacklist["strategies"]:
            return False

        # Si se especifica símbolo, verificar si está en la lista de símbolos bloqueados para esta estrategia
        if symbol:
            return symbol in self.blacklist["strategies"][strategy].get("symbols", [])

        return True

    def get_blacklist_reason(self, symbol: str) -> Optional[str]:
        """Obtener razón de blacklist para un símbolo"""
        if symbol in self.blacklist["symbols"]:
            return self.blacklist["symbols"][symbol].get(
                "reason", "Símbolo en blacklist"
            )
        return None

    def add_symbol_to_blacklist(
        self, symbol: str, reason: str, loss_amount: float = None
    ):
        """Agregar símbolo a la blacklist manualmente"""
        self.blacklist["symbols"][symbol] = {
            "reason": reason,
            "added_date": datetime.now().isoformat(),
            "loss_amount": loss_amount,
            "loss_percentage": abs(loss_amount) / 1152.79
            if loss_amount
            else None,  # Basado en pérdida total del análisis
        }
        self._save_blacklist(self.blacklist)
        self.logger.warning(f"🚫 Símbolo {symbol} agregado a blacklist: {reason}")

    def remove_symbol_from_blacklist(self, symbol: str) -> bool:
        """Remover símbolo de la blacklist"""
        if symbol in self.blacklist["symbols"]:
            del self.blacklist["symbols"][symbol]
            self._save_blacklist(self.blacklist)
            self.logger.info(f"✅ Símbolo {symbol} removido de blacklist")
            return True
        return False

    def get_blacklisted_symbols(self) -> List[str]:
        """Obtener lista de símbolos en blacklist"""
        return list(self.blacklist["symbols"].keys())

    def get_blacklist_status(self) -> Dict:
        """
        Obtener estado completo de la blacklist.

        Returns:
            Dict con símbolos, estrategias y metadatos de estado.
        """
        symbols = self.blacklist.get("symbols", {})
        strategies = self.blacklist.get("strategies", {})
        return {
            "symbols": symbols,
            "strategies": strategies,
            "symbols_count": len(symbols),
            "strategies_count": len(strategies),
            "active": len(symbols) > 0,
            "updated_at": datetime.now().isoformat(),
        }

    def get_blacklist_summary(self) -> str:
        """Obtener resumen de la blacklist"""
        symbols_count = len(self.blacklist["symbols"])
        strategies_count = len(self.blacklist["strategies"])

        summary = f"🚫 BLACKLIST SUMMARY: {symbols_count} símbolos, {strategies_count} estrategias\n\n"

        if symbols_count > 0:
            summary += "📊 SÍMBOLOS BLOQUEADOS:\n"
            for symbol, info in self.blacklist["symbols"].items():
                loss = info.get("loss_amount", 0)
                summary += (
                    f"  🚫 {symbol}: {info['reason']} (Pérdida: {loss:.2f} USDT)\n"
                )

        if strategies_count > 0:
            summary += "\n📊 ESTRATEGIAS BLOQUEADAS:\n"
            for strategy, info in self.blacklist["strategies"].items():
                symbols = info.get("symbols", [])
                summary += f"  🚫 {strategy}: {info['reason']} (Símbolos: {', '.join(symbols)})\n"

        return summary

    async def auto_analyze_and_blacklist(self) -> Dict[str, List[str]]:
        """
        Analizar automáticamente pérdidas y agregar símbolos a blacklist si exceden umbrales

        Returns:
            Dict con símbolos agregados automáticamente
        """
        try:
            db = SessionLocal()
            auto_added = {"symbols": [], "reasons": []}

            # Analizar pérdidas por símbolo
            symbol_losses = (
                db.query(
                    Trade.symbol,
                    func.sum(Trade.profit_loss).label("total_loss"),
                    func.count(Trade.id).label("trade_count"),
                )
                .filter(Trade.profit_loss.isnot(None), Trade.profit_loss < 0)
                .group_by(Trade.symbol)
                .all()
            )

            thresholds = self.blacklist["auto_blacklist_thresholds"]

            for symbol, total_loss, trade_count in symbol_losses:
                # Verificar si ya está en blacklist
                if self.is_symbol_blacklisted(symbol):
                    continue

                # Verificar umbrales
                if (
                    total_loss <= thresholds["max_loss_per_symbol"]
                    and trade_count >= thresholds["min_trades_for_analysis"]
                ):
                    reason = f"Auto-blacklist: Pérdida {total_loss:.2f} USDT en {trade_count} trades"
                    self.add_symbol_to_blacklist(symbol, reason, float(total_loss))
                    auto_added["symbols"].append(symbol)
                    auto_added["reasons"].append(reason)

            db.close()

            if auto_added["symbols"]:
                self.logger.warning(
                    f"🤖 Auto-blacklist activado: {auto_added['symbols']}"
                )

            return auto_added

        except Exception as e:
            self.logger.error(f"Error en auto-análisis: {e}")
            return {"symbols": [], "reasons": []}

    def should_block_trading(
        self, symbol: str, strategy: str = None
    ) -> tuple[bool, str]:
        """
        Verificar si se debe bloquear trading para un símbolo/estrategia

        Returns:
            Tuple[bool, str]: (bloquear, razón)
        """
        # Verificar símbolo
        if self.is_symbol_blacklisted(symbol):
            reason = self.get_blacklist_reason(symbol)
            return True, f"Símbolo {symbol} en blacklist: {reason}"

        # Verificar estrategia
        if strategy and self.is_strategy_blacklisted(strategy, symbol):
            return True, f"Estrategia {strategy} bloqueada para {symbol}"

        return False, "Trading permitido"

    def is_blacklist_active(self) -> bool:
        """Verificar si la blacklist está activa (tiene símbolos bloqueados)"""
        try:
            return len(self.blacklist.get("symbols", {})) > 0
        except Exception as e:
            self.logger.error(f"Error verificando estado de blacklist: {e}")
            return False


# Instancia global para uso en el sistema
strategy_blacklist = StrategyBlacklist()
