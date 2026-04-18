"""
Router para endpoints de portfolio y posiciones.
performance-analyzer-realdata-agent: añade endpoints de snapshot histórico
para dashboards y Grafana.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from decimal import Decimal
from pydantic import BaseModel

from app.models.portfolio_schemas import PortfolioSummary, AssetSummary, PositionsResponse, Position
from app.services.binance_service import BinanceService
from app.db.session import SessionLocal
from sqlalchemy import text

from app.services.portfolio_snapshot_service import (
    get_portfolio_value_history,
    get_latest_snapshot,
    get_snapshot_count,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ---------------------------------------------------------------------------
# Schemas de respuesta para endpoints de snapshot
# ---------------------------------------------------------------------------

class SnapshotPoint(BaseModel):
    """Punto de dato de valor del portafolio"""
    timestamp: datetime
    total_value_usdt: float
    usdt_free: float
    btc_value_usdt: float
    other_assets_usdt: float
    btc_price: Optional[float] = None


class PortfolioHistoryResponse(BaseModel):
    """Respuesta del historial del portafolio"""
    days: int
    snapshot_count: int
    total_snapshots_stored: int
    values: List[float]
    timestamps: List[datetime]
    latest_value_usdt: Optional[float] = None
    data_available: bool


async def get_binance_service() -> BinanceService:
    """Dependency para obtener el servicio de Binance"""
    return BinanceService()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    binance_service: BinanceService = Depends(get_binance_service)
) -> PortfolioSummary:
    """
    Obtiene el resumen completo del portfolio desde Binance.
    
    Returns:
        PortfolioSummary: Resumen del portfolio con balances y valores en USDT
    """
    try:
        logger.info("📊 Obteniendo resumen del portfolio desde Binance...")
        
        # Obtener cuenta completa desde Binance (optimizado con cache)
        account_info = await binance_service.get_account_optimized()
        
        if not account_info or 'balances' not in account_info:
            raise HTTPException(
                status_code=500, 
                detail="No se pudo obtener información de la cuenta desde Binance"
            )
        
        balances = account_info['balances']
        assets: List[AssetSummary] = []
        portfolio_total_usdt = Decimal('0.0')
        cash_usdt = Decimal('0.0')
        
        # Umbral mínimo para filtrar "polvo" (balances muy pequeños)
        MIN_BALANCE_THRESHOLD = Decimal('0.00001')
        
        for balance in balances:
            free = Decimal(str(balance['free']))
            locked = Decimal(str(balance['locked']))
            total_balance = free + locked
            
            # Filtrar balances muy pequeños
            if total_balance < MIN_BALANCE_THRESHOLD:
                continue
                
            asset = balance['asset']
            
            # Calcular valor en USDT
            if asset == 'USDT':
                total_usdt_value = total_balance
                cash_usdt = free  # Balance libre de USDT
            else:
                # Para otros activos, necesitaríamos obtener el precio
                # Por simplicidad, asumimos que el valor es 0 si no es USDT
                # En un sistema real, aquí se consultaría el precio del activo
                total_usdt_value = Decimal('0.0')
            
            assets.append(AssetSummary(
                asset=asset,
                free=float(free),
                locked=float(locked),
                total_usdt_value=float(total_usdt_value)
            ))
            
            portfolio_total_usdt += total_usdt_value
        
        # Agregar USDT al total si no estaba en la lista
        if not any(asset.asset == 'USDT' for asset in assets):
            assets.append(AssetSummary(
                asset='USDT',
                free=float(cash_usdt),
                locked=0.0,
                total_usdt_value=float(cash_usdt)
            ))
            portfolio_total_usdt += cash_usdt
        
        logger.info(f"✅ Portfolio resumido: {len(assets)} activos, Total: {portfolio_total_usdt} USDT")
        
        return PortfolioSummary(
            cash_usdt=float(cash_usdt),
            portfolio_total_usdt=float(portfolio_total_usdt),
            assets=assets
        )
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen del portfolio: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno obteniendo resumen del portfolio: {str(e)}"
        )


@router.get("/positions", response_model=PositionsResponse)
async def get_portfolio_positions() -> PositionsResponse:
    """
    Obtiene las posiciones abiertas gestionadas por GridBot.
    
    Returns:
        PositionsResponse: Lista de posiciones abiertas
    """
    try:
        logger.info("📋 Obteniendo posiciones abiertas desde la base de datos...")
        
        # Por ahora, devolver lista vacía ya que no hay tabla positions
        # En el futuro, cuando se implemente la tabla positions, usar:
        # async with AsyncSessionLocal() as session:
        #     result = await session.execute(text("SELECT ... FROM positions ..."))
        
        logger.info("✅ Posiciones obtenidas: 0 posiciones abiertas (tabla positions no implementada)")
        
        return PositionsResponse(
            positions=[],
            total_count=0
        )
            
    except Exception as e:
        logger.error(f"❌ Error obteniendo posiciones: {e}")
        # En caso de error, devolver lista vacía en lugar de fallar
        return PositionsResponse(
            positions=[],
            total_count=0
        )


# Endpoint directo para /api/positions (compatibilidad con auditoría)
@router.get("/", response_model=PositionsResponse, include_in_schema=False)
async def get_positions_direct() -> PositionsResponse:
    """
    Endpoint directo para /api/positions (compatibilidad con auditoría).
    Redirige a get_portfolio_positions.
    """
    return await get_portfolio_positions()


# ---------------------------------------------------------------------------
# performance-analyzer-realdata-agent: endpoints de historial real
# ---------------------------------------------------------------------------

@router.get("/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    days: int = Query(default=30, ge=1, le=365, description="Días de historial"),
) -> PortfolioHistoryResponse:
    """
    Retorna el historial real de valores del portafolio desde PostgreSQL.

    Los datos provienen de la tabla portfolio_snapshots (captura cada 15 min).
    Útil para dashboards de Grafana y análisis de rendimiento.
    """
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        from app.models.portfolio_snapshot import PortfolioSnapshot

        rows = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.captured_at >= since)
            .order_by(PortfolioSnapshot.captured_at.asc())
            .all()
        )

        total_stored = get_snapshot_count(db)
        latest = get_latest_snapshot(db)

        values = [float(r.total_value_usdt) for r in rows]
        timestamps = [r.captured_at for r in rows]

        return PortfolioHistoryResponse(
            days=days,
            snapshot_count=len(rows),
            total_snapshots_stored=total_stored,
            values=values,
            timestamps=timestamps,
            latest_value_usdt=float(latest.total_value_usdt) if latest else None,
            data_available=len(rows) >= 2,
        )
    except Exception as exc:
        logger.error("[portfolio/history] Error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.get("/snapshot/latest", response_model=SnapshotPoint)
async def get_latest_portfolio_snapshot() -> SnapshotPoint:
    """
    Retorna el snapshot más reciente del portafolio.
    Si no hay snapshots disponibles retorna 404.
    """
    db = SessionLocal()
    try:
        snapshot = get_latest_snapshot(db)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail="No hay snapshots disponibles. "
                       "Espere que capture_portfolio_snapshot se ejecute (cada 15 min).",
            )
        return SnapshotPoint(
            timestamp=snapshot.captured_at,
            total_value_usdt=float(snapshot.total_value_usdt),
            usdt_free=float(snapshot.usdt_free),
            btc_value_usdt=float(snapshot.btc_value_usdt),
            other_assets_usdt=float(snapshot.other_assets_usdt),
            btc_price=float(snapshot.btc_price) if snapshot.btc_price else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[portfolio/snapshot/latest] Error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()
