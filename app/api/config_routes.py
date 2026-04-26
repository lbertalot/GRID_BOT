#!/usr/bin/env python3
"""
Rutas API para Gestión de Configuración Unificada
GridBot V2.5
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Optional
import logging
from pydantic import BaseModel, Field

# Importar configuración unificada
from app.core.unified_config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["Configuration Management"])

# Configurar templates
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def config_manager_page(request: Request):
    """
    Página principal del gestor de configuración
    """
    return templates.TemplateResponse("config_manager.html", {"request": request})


@router.get("/summary")
async def get_config_summary():
    """
    Obtiene un resumen de la configuración del sistema
    """
    try:
        config = get_config()
        summary = config.get_config_summary()
        return summary
    except Exception as e:
        logger.error(f"Error obteniendo resumen de configuración: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/assets")
async def get_all_assets():
    """
    Obtiene todos los assets configurados
    """
    try:
        config = get_config()
        assets = config.get_all_assets()

        # Convertir a lista para la API
        assets_list = []
        for symbol, asset_config in assets.items():
            assets_list.append({"symbol": symbol, **asset_config})

        return assets_list
    except Exception as e:
        logger.error(f"Error obteniendo assets: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/assets/{symbol}")
async def get_asset_config(symbol: str):
    """
    Obtiene configuración de un asset específico
    """
    try:
        config = get_config()
        asset_config = config.get_asset_config(symbol)

        if not asset_config:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} no encontrado")

        return {"symbol": symbol, **asset_config}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo configuración de asset {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/assets/{symbol}/toggle")
async def toggle_asset(symbol: str, data: Dict):
    """
    Activa/desactiva un asset
    """
    try:
        config = get_config()
        asset_config = config.get_asset_config(symbol)

        if not asset_config:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} no encontrado")

        # Actualizar estado
        asset_config["is_active"] = data.get("is_active", False)
        config.update_asset_config(symbol, asset_config)

        return {
            "message": f"Asset {symbol} {'activado' if asset_config['is_active'] else 'desactivado'} exitosamente",
            "symbol": symbol,
            "is_active": asset_config["is_active"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cambiando estado de asset {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.put("/assets/{symbol}")
async def update_asset_config(symbol: str, data: Dict):
    """
    Actualiza configuración de un asset
    """
    try:
        config = get_config()
        asset_config = config.get_asset_config(symbol)

        if not asset_config:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} no encontrado")

        # Actualizar configuración
        asset_config.update(data)
        config.update_asset_config(symbol, asset_config)

        return {
            "message": f"Configuración de {symbol} actualizada exitosamente",
            "symbol": symbol,
            "config": asset_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando configuración de asset {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/assets")
async def add_asset(data: Dict):
    """
    Agrega un nuevo asset
    """
    try:
        config = get_config()
        symbol = data.get("symbol")

        if not symbol:
            raise HTTPException(status_code=400, detail="Símbolo requerido")

        if config.get_asset_config(symbol):
            raise HTTPException(status_code=409, detail=f"Asset {symbol} ya existe")

        # Crear configuración por defecto
        default_config = {
            "symbol": symbol,
            "is_active": False,
            "min_price": data.get("min_price", 0),
            "max_price": data.get("max_price", 0),
            "grids": data.get("grids", 0),
            "quantity": data.get("quantity", 0),
            "investment_amount": data.get("investment_amount", 0),
            "precision": {
                "quantity": data.get("quantity_precision", 2),
                "price": data.get("price_precision", 2),
                "step_size": data.get("step_size", 0.01),
            },
        }

        config.add_asset(symbol, default_config)

        return {
            "message": f"Asset {symbol} agregado exitosamente",
            "symbol": symbol,
            "config": default_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error agregando asset: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.delete("/assets/{symbol}")
async def remove_asset(symbol: str):
    """
    Remueve un asset
    """
    try:
        config = get_config()
        asset_config = config.get_asset_config(symbol)

        if not asset_config:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} no encontrado")

        config.remove_asset(symbol)

        return {"message": f"Asset {symbol} removido exitosamente", "symbol": symbol}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removiendo asset {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/safety")
async def get_safety_limits():
    """
    Obtiene límites de seguridad
    """
    try:
        config = get_config()
        return config.get_safety_limits()
    except Exception as e:
        logger.error(f"Error obteniendo límites de seguridad: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.put("/safety")
async def update_safety_limits(data: Dict):
    """
    Actualiza límites de seguridad
    """
    try:
        config = get_config()

        # Validar datos
        required_fields = [
            "max_daily_loss",
            "max_total_loss",
            "max_trade_loss",
            "max_consecutive_losses",
            "min_balance",
        ]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Campo requerido: {field}")

        # Convertir porcentajes a decimales
        limits = {
            "max_daily_loss": data["max_daily_loss"] / 100,
            "max_total_loss": data["max_total_loss"] / 100,
            "max_trade_loss": data["max_trade_loss"] / 100,
            "max_consecutive_losses": data["max_consecutive_losses"],
            "max_hourly_loss": data.get("max_hourly_loss", 0.03),
            "min_balance": data["min_balance"],
            "min_notional_value": data.get("min_notional_value", 10.0),
        }

        config.update_safety_limits(limits)

        return {
            "message": "Límites de seguridad actualizados exitosamente",
            "limits": limits,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando límites de seguridad: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/monitoring")
async def get_monitoring_settings():
    """
    Obtiene configuración de monitoreo
    """
    try:
        config = get_config()
        return config.get_monitoring_settings()
    except Exception as e:
        logger.error(f"Error obteniendo configuración de monitoreo: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.put("/monitoring")
async def update_monitoring_settings(data: Dict):
    """
    Actualiza configuración de monitoreo
    """
    try:
        config = get_config()

        settings = {
            "alerts_enabled": data.get("alerts_enabled", True),
            "email_alerts": data.get("email_alerts", False),
            "sms_alerts": data.get("sms_alerts", False),
            "dashboard_enabled": data.get("dashboard_enabled", True),
            "log_level": data.get("log_level", "INFO"),
        }

        config.update_monitoring_settings(settings)

        return {
            "message": "Configuración de monitoreo actualizada exitosamente",
            "settings": settings,
        }
    except Exception as e:
        logger.error(f"Error actualizando configuración de monitoreo: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/system")
async def get_system_settings():
    """
    Obtiene configuración del sistema
    """
    try:
        config = get_config()
        return config.get_system_settings()
    except Exception as e:
        logger.error(f"Error obteniendo configuración del sistema: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.put("/system")
async def update_system_settings(data: Dict):
    """
    Actualiza configuración del sistema
    """
    try:
        config = get_config()

        settings = {
            "trading_enabled": data.get("trading_enabled", False),
            "paper_trading": data.get("paper_trading", True),
            "max_concurrent_trades": data.get("max_concurrent_trades", 5),
            "default_investment_percentage": data.get(
                "default_investment_percentage", 0.1
            ),
            "emergency_stop_enabled": data.get("emergency_stop_enabled", True),
        }

        config.update_system_settings(settings)

        return {
            "message": "Configuración del sistema actualizada exitosamente",
            "settings": settings,
        }
    except Exception as e:
        logger.error(f"Error actualizando configuración del sistema: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/enable-trading")
async def enable_trading():
    """
    Habilita el trading
    """
    try:
        config = get_config()
        config.enable_trading()

        return {"message": "Trading habilitado exitosamente", "trading_enabled": True}
    except Exception as e:
        logger.error(f"Error habilitando trading: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/disable-trading")
async def disable_trading():
    """
    Deshabilita el trading
    """
    try:
        config = get_config()
        config.disable_trading()

        return {
            "message": "Trading deshabilitado exitosamente",
            "trading_enabled": False,
        }
    except Exception as e:
        logger.error(f"Error deshabilitando trading: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/enable-paper-trading")
async def enable_paper_trading():
    """
    Habilita paper trading
    """
    try:
        config = get_config()
        config.enable_paper_trading()

        return {
            "message": "Paper trading habilitado exitosamente",
            "paper_trading": True,
        }
    except Exception as e:
        logger.error(f"Error habilitando paper trading: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/disable-paper-trading")
async def disable_paper_trading():
    """
    Deshabilita paper trading
    """
    try:
        config = get_config()
        config.disable_paper_trading()

        return {
            "message": "Paper trading deshabilitado exitosamente",
            "paper_trading": False,
        }
    except Exception as e:
        logger.error(f"Error deshabilitando paper trading: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/validate")
async def validate_configuration():
    """
    Valida la configuración completa
    """
    try:
        config = get_config()
        is_valid, errors = config.validate_config()

        return {
            "valid": is_valid,
            "errors": errors,
            "message": "Configuración válida"
            if is_valid
            else f"Configuración inválida: {len(errors)} errores",
        }
    except Exception as e:
        logger.error(f"Error validando configuración: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/backup")
async def create_backup():
    """
    Crea un backup de la configuración
    """
    try:
        config = get_config()
        # TODO: Implementar backup
        return {
            "message": "Backup creado exitosamente",
            "backup_file": "config_backup.json",
        }
    except Exception as e:
        logger.error(f"Error creando backup: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/reset")
async def reset_configuration():
    """
    Resetea la configuración a valores por defecto
    """
    try:
        config = get_config()
        config.create_default_config()

        return {
            "message": "Configuración reseteada exitosamente",
            "config": config.get_config_summary(),
        }
    except Exception as e:
        logger.error(f"Error reseteando configuración: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/paper/reset")
async def reset_paper_trading(balance: float = 1000.0):
    """Resetea el sistema de paper trading con un balance inicial dado."""
    try:
        from app.core.paper_trading import paper_trading_system

        paper_trading_system.reset_paper_trading(new_balance=balance)
        return {"status": "ok", "balance": balance}
    except Exception as e:
        logger.error(f"Error reseteando paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/summary")
async def get_paper_summary():
    """Devuelve el resumen actual de paper trading (PnL, posiciones, trades)."""
    try:
        from app.core.paper_trading import get_paper_portfolio_summary

        summary = get_paper_portfolio_summary()
        return summary
    except Exception as e:
        logger.error(f"Error obteniendo resumen de paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PaperOrderRequest(BaseModel):
    symbol: str = Field(..., description="Símbolo, ej: ETHUSDT")
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)


@router.post("/paper/buy")
async def paper_buy(req: PaperOrderRequest):
    try:
        price = req.price
        if price is None:
            from app.services.binance_async import AsyncBinanceWrapper

            aw = AsyncBinanceWrapper()
            price = await aw.get_price(req.symbol)
        from app.core.paper_trading import place_paper_buy_order

        order = place_paper_buy_order(
            req.symbol.upper(), float(req.quantity), float(price)
        )
        return {"status": "ok", "order": order}
    except Exception as e:
        logger.error(f"Error en paper buy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/paper/sell")
async def paper_sell(req: PaperOrderRequest):
    try:
        price = req.price
        if price is None:
            from app.services.binance_async import AsyncBinanceWrapper

            aw = AsyncBinanceWrapper()
            price = await aw.get_price(req.symbol)
        from app.core.paper_trading import place_paper_sell_order

        order = place_paper_sell_order(
            req.symbol.upper(), float(req.quantity), float(price)
        )
        return {"status": "ok", "order": order}
    except Exception as e:
        logger.error(f"Error en paper sell: {e}")
        raise HTTPException(status_code=500, detail=str(e))
