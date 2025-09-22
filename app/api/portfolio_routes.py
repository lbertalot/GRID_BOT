"""
Router para endpoints de portfolio y posiciones
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from decimal import Decimal

from app.models.portfolio_schemas import PortfolioSummary, AssetSummary, PositionsResponse, Position
from app.services.binance_service import BinanceService
from app.db.session import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


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
