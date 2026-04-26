"""
Endpoints para métricas de rentabilidad y Prometheus
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from typing import Optional
import logging

from app.services.metrics_service import metrics_service
from app.core.auth import get_api_key_user
from app.db.session import SessionLocal
from app.models.system_setting import SystemSetting
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/prometheus")
async def get_prometheus_metrics():
    """
    Endpoint para métricas de Prometheus
    """
    try:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generando métricas de Prometheus: {e}")
        raise HTTPException(status_code=500, detail="Error generando métricas")


@router.post("/baseline/reset")
async def reset_baseline(user=Depends(get_api_key_user)):
    """Fija la baseline actual para total_profit y portfolio_change (persistente en BD)."""
    try:
        # Capturar valor actual de portafolio desde el servicio de métricas
        out = await metrics_service.calculate_portfolio_metrics()
        current_value = float(out.get("portfolio_value", 0.0) or 0.0)

        db = SessionLocal()
        try:
            # total_profit baseline ya existe en MetricsService; fijamos la de portafolio
            s = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "portfolio:baseline_value_usdt")
                .first()
            )
            if s:
                s.value = str(current_value)
            else:
                s = SystemSetting(
                    key="portfolio:baseline_value_usdt", value=str(current_value)
                )
                db.add(s)
            # Baseline de PnL acumulado (fecha desde la cual computar total_profit)
            from datetime import datetime

            now_iso = datetime.utcnow().isoformat()
            p = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "profit:baseline_iso")
                .first()
            )
            if p:
                p.value = now_iso
            else:
                p = SystemSetting(key="profit:baseline_iso", value=now_iso)
                db.add(p)
            db.commit()
        finally:
            db.close()

        return {
            "status": "ok",
            "baseline_portfolio_usdt": current_value,
            "profit_baseline_iso": now_iso,
        }
    except Exception as e:
        logger.error(f"Error reseteando baseline: {e}")
        raise HTTPException(status_code=500, detail="Error reseteando baseline")


@router.get("/baseline/reset")
async def reset_baseline_get(token: Optional[str] = None):
    """Versión GET para usar desde Grafana (opcional token DASH_RESET_TOKEN)."""
    try:
        required = os.getenv("DASH_RESET_TOKEN")
        if required and token != required:
            raise HTTPException(status_code=401, detail="Unauthorized")

        out = await metrics_service.calculate_portfolio_metrics()
        current_value = float(out.get("portfolio_value", 0.0) or 0.0)

        db = SessionLocal()
        from datetime import datetime

        now_iso = datetime.utcnow().isoformat()
        try:
            s = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "portfolio:baseline_value_usdt")
                .first()
            )
            if s:
                s.value = str(current_value)
            else:
                s = SystemSetting(
                    key="portfolio:baseline_value_usdt", value=str(current_value)
                )
                db.add(s)
            p = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "profit:baseline_iso")
                .first()
            )
            if p:
                p.value = now_iso
            else:
                p = SystemSetting(key="profit:baseline_iso", value=now_iso)
                db.add(p)
            db.commit()
        finally:
            db.close()
        return {
            "status": "ok",
            "baseline_portfolio_usdt": current_value,
            "profit_baseline_iso": now_iso,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reseteando baseline (GET): {e}")
        raise HTTPException(status_code=500, detail="Error reseteando baseline")


@router.get("/profitability")
async def get_profitability_metrics(user=Depends(get_api_key_user)):
    """
    Obtiene métricas de rentabilidad en formato JSON
    """
    try:
        metrics = await metrics_service.calculate_portfolio_metrics()

        if not metrics:
            return {
                "error": "No se pudieron calcular las métricas",
                "portfolio_value": 0.0,
                "total_profit": 0.0,
                "daily_profit": 0.0,
                "roi_daily": 0.0,
                "asset_metrics": {},
            }

        return {"success": True, "data": metrics}

    except Exception as e:
        logger.error(f"Error obteniendo métricas de rentabilidad: {e}")
        raise HTTPException(status_code=500, detail="Error calculando métricas")


@router.get("/summary")
async def get_metrics_summary(user=Depends(get_api_key_user)):
    """
    Obtiene un resumen de las métricas más importantes
    """
    try:
        metrics = await metrics_service.calculate_portfolio_metrics()

        if not metrics:
            return {
                "portfolio_value": 0.0,
                "total_profit": 0.0,
                "daily_profit": 0.0,
                "roi_daily": 0.0,
                "status": "No disponible",
            }

        # Determinar estado del bot basado en las métricas
        status = "Activo"
        if metrics.get("total_profit", 0) < 0:
            status = "Pérdidas"
        elif metrics.get("roi_daily", 0) > 5:
            status = "Excelente"
        elif metrics.get("roi_daily", 0) > 0:
            status = "Ganando"

        return {
            "portfolio_value": round(metrics.get("portfolio_value", 0), 2),
            "total_profit": round(metrics.get("total_profit", 0), 2),
            "daily_profit": round(metrics.get("daily_profit", 0), 2),
            "roi_daily": round(metrics.get("roi_daily", 0), 2),
            "status": status,
            "last_update": metrics.get("last_update", ""),
        }

    except Exception as e:
        logger.error(f"Error obteniendo resumen de métricas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo resumen")


@router.get("/assets")
async def get_asset_metrics(user=Depends(get_api_key_user)):
    """
    Obtiene métricas específicas por activo
    """
    try:
        metrics = await metrics_service.calculate_portfolio_metrics()

        if not metrics:
            return {"assets": []}

        asset_metrics = metrics.get("asset_metrics", {})

        # Formatear métricas por activo
        formatted_assets = []
        for asset, data in asset_metrics.items():
            formatted_assets.append(
                {
                    "asset": asset,
                    "profit": round(data.get("profit", 0), 2),
                    "roi": round(data.get("roi", 0), 2),
                    "balance": round(data.get("balance", 0), 6),
                    "status": "Ganando" if data.get("profit", 0) > 0 else "Perdiendo",
                }
            )

        return {"assets": formatted_assets}

    except Exception as e:
        logger.error(f"Error obteniendo métricas por activo: {e}")
        raise HTTPException(
            status_code=500, detail="Error obteniendo métricas por activo"
        )
