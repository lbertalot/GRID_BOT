#!/usr/bin/env python3
"""
Sistema de Configuración Unificado para GridBot V2.5
Centraliza toda la configuración del sistema en un solo lugar
"""

import json
import os
import logging
from typing import Dict, Optional, Tuple, List
from datetime import datetime

from app.core.capital_risk import daily_loss_limit_fraction

logger = logging.getLogger(__name__)


def _sot_max_daily_loss() -> float:
    """Daily loss SoT (ADR-003 / B3): magnitud positiva, default 0.03."""
    return float(daily_loss_limit_fraction())


class UnifiedConfig:
    """
    Sistema de configuración unificado
    """

    def __init__(self, config_file: str = "grid_config_optimized.json"):
        self.config_file = config_file
        self.config = {}
        self.load_config()

    def load_config(self):
        """Carga la configuración desde archivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                logger.info(f"✅ Configuración cargada desde {self.config_file}")
            else:
                logger.warning(
                    f"⚠️ Archivo de configuración no encontrado: {self.config_file}"
                )
                self.create_default_config()
        except Exception as e:
            logger.error(f"❌ Error cargando configuración: {e}")
            self.create_default_config()

    def save_config(self):
        """Guarda la configuración en archivo"""
        try:
            # Agregar metadata de actualización
            self.config["_metadata"] = {
                "last_updated": datetime.now().isoformat(),
                "version": "2.5_unified",
                "total_assets": len(
                    [k for k in self.config.keys() if not k.startswith("_")]
                ),
            }

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Configuración guardada en {self.config_file}")
        except Exception as e:
            logger.error(f"❌ Error guardando configuración: {e}")

    def create_default_config(self):
        """Crea configuración por defecto"""
        self.config = {
            "_metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "2.5_unified",
                "description": "Configuración unificada por defecto",
            },
            "_system_settings": {
                "trading_enabled": False,
                "paper_trading": True,
                "max_concurrent_trades": 5,
                "default_investment_percentage": 0.1,
                "emergency_stop_enabled": True,
            },
            "_safety_limits": {
                "max_daily_loss": _sot_max_daily_loss(),
                "max_total_loss": 0.10,
                "max_trade_loss": 0.02,
                "max_consecutive_losses": 3,
                "max_hourly_loss": 0.03,
                "min_balance": 50.0,
                "min_notional_value": 10.0,
            },
            "_monitoring_settings": {
                "alerts_enabled": True,
                "email_alerts": False,
                "sms_alerts": False,
                "dashboard_enabled": True,
                "log_level": "INFO",
            },
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "is_active": False,
                "min_price": 108000,
                "max_price": 109000,
                "grids": 0,
                "quantity": 0,
                "investment_amount": 0,
                "precision": {"quantity": 5, "price": 2, "step_size": 0.00001},
            },
            "ETHUSDT": {
                "symbol": "ETHUSDT",
                "is_active": False,
                "min_price": 4400,
                "max_price": 4410,
                "grids": 0,
                "quantity": 0,
                "investment_amount": 0,
                "precision": {"quantity": 4, "price": 2, "step_size": 0.0001},
            },
        }

        self.save_config()
        logger.info("✅ Configuración por defecto creada")

    def get_asset_config(self, symbol: str) -> Optional[Dict]:
        """
        Obtiene configuración de un asset específico

        Args:
            symbol: Símbolo del trading pair

        Returns:
            Dict: Configuración del asset o None si no existe
        """
        return self.config.get(symbol)

    def update_asset_config(self, symbol: str, config: Dict):
        """
        Actualiza configuración de un asset

        Args:
            symbol: Símbolo del trading pair
            config: Nueva configuración
        """
        self.config[symbol] = config
        self.save_config()
        logger.info(f"✅ Configuración actualizada para {symbol}")

    def get_system_settings(self) -> Dict:
        """Obtiene configuración del sistema"""
        return self.config.get("_system_settings", {})

    def update_system_settings(self, settings: Dict):
        """Actualiza configuración del sistema"""
        self.config["_system_settings"] = settings
        self.save_config()
        logger.info("✅ Configuración del sistema actualizada")

    def get_safety_limits(self) -> Dict:
        """Obtiene límites de seguridad.

        `max_daily_loss` siempre se sobrescribe con el SoT de capital_risk
        (ADR-003 / B3) para que un JSON stale con 0.05 no mande en runtime.
        """
        limits = dict(self.config.get("_safety_limits", {}))
        limits["max_daily_loss"] = _sot_max_daily_loss()
        return limits

    def update_safety_limits(self, limits: Dict):
        """Actualiza límites de seguridad (coerciona daily loss al SoT)."""
        merged = dict(limits)
        merged["max_daily_loss"] = _sot_max_daily_loss()
        self.config["_safety_limits"] = merged
        self.save_config()
        logger.info("✅ Límites de seguridad actualizados")

    def get_monitoring_settings(self) -> Dict:
        """Obtiene configuración de monitoreo"""
        return self.config.get("_monitoring_settings", {})

    def update_monitoring_settings(self, settings: Dict):
        """Actualiza configuración de monitoreo"""
        self.config["_monitoring_settings"] = settings
        self.save_config()
        logger.info("✅ Configuración de monitoreo actualizada")

    def get_active_assets(self) -> Dict[str, Dict]:
        """Obtiene todos los assets activos"""
        active_assets = {}
        for symbol, config in self.config.items():
            if not symbol.startswith("_") and config.get("is_active", False):
                active_assets[symbol] = config
        return active_assets

    def get_all_assets(self) -> Dict[str, Dict]:
        """Obtiene todos los assets configurados"""
        assets = {}
        for symbol, config in self.config.items():
            if not symbol.startswith("_"):
                assets[symbol] = config
        return assets

    def add_asset(self, symbol: str, config: Dict):
        """
        Agrega un nuevo asset

        Args:
            symbol: Símbolo del trading pair
            config: Configuración del asset
        """
        self.config[symbol] = config
        self.save_config()
        logger.info(f"✅ Asset agregado: {symbol}")

    def remove_asset(self, symbol: str):
        """
        Remueve un asset

        Args:
            symbol: Símbolo del trading pair
        """
        if symbol in self.config:
            del self.config[symbol]
            self.save_config()
            logger.info(f"✅ Asset removido: {symbol}")
        else:
            logger.warning(f"⚠️ Asset no encontrado: {symbol}")

    def enable_trading(self):
        """Habilita el trading"""
        self.config["_system_settings"]["trading_enabled"] = True
        self.save_config()
        logger.info("✅ Trading habilitado")

    def disable_trading(self):
        """Deshabilita el trading"""
        self.config["_system_settings"]["trading_enabled"] = False
        self.save_config()
        logger.info("✅ Trading deshabilitado")

    def enable_paper_trading(self):
        """Habilita paper trading"""
        self.config["_system_settings"]["paper_trading"] = True
        self.save_config()
        logger.info("✅ Paper trading habilitado")

    def disable_paper_trading(self):
        """Deshabilita paper trading"""
        self.config["_system_settings"]["paper_trading"] = False
        self.save_config()
        logger.info("✅ Paper trading deshabilitado")

    def get_config_summary(self) -> Dict:
        """Obtiene un resumen de la configuración"""
        active_assets = self.get_active_assets()
        all_assets = self.get_all_assets()

        return {
            "metadata": self.config.get("_metadata", {}),
            "system_settings": self.get_system_settings(),
            "safety_limits": self.get_safety_limits(),
            "monitoring_settings": self.get_monitoring_settings(),
            "assets_summary": {
                "total_assets": len(all_assets),
                "active_assets": len(active_assets),
                "inactive_assets": len(all_assets) - len(active_assets),
            },
            "active_assets": list(active_assets.keys()),
        }

    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        Valida la configuración completa

        Returns:
            Tuple[bool, List[str]]: (válido, lista de errores)
        """
        errors = []

        # Validar configuración del sistema
        system_settings = self.get_system_settings()
        if not isinstance(system_settings.get("max_concurrent_trades"), int):
            errors.append("max_concurrent_trades debe ser un entero")

        # Validar límites de seguridad
        safety_limits = self.get_safety_limits()
        for limit_name, limit_value in safety_limits.items():
            if not isinstance(limit_value, (int, float)) or limit_value < 0:
                errors.append(f"Límite {limit_name} debe ser un número positivo")

        # Validar assets
        for symbol, config in self.get_all_assets().items():
            if not isinstance(config.get("is_active"), bool):
                errors.append(f"is_active debe ser boolean para {symbol}")

            if not isinstance(config.get("min_price"), (int, float)):
                errors.append(f"min_price debe ser número para {symbol}")

            if not isinstance(config.get("max_price"), (int, float)):
                errors.append(f"max_price debe ser número para {symbol}")

        return len(errors) == 0, errors


# Instancia global de configuración unificada
unified_config = UnifiedConfig()


def get_config() -> UnifiedConfig:
    """Función de conveniencia para obtener la configuración"""
    return unified_config


def get_asset_config(symbol: str) -> Optional[Dict]:
    """Función de conveniencia para obtener configuración de asset"""
    return unified_config.get_asset_config(symbol)


def get_system_settings() -> Dict:
    """Función de conveniencia para obtener configuración del sistema"""
    return unified_config.get_system_settings()


def get_safety_limits() -> Dict:
    """Función de conveniencia para obtener límites de seguridad"""
    return unified_config.get_safety_limits()
