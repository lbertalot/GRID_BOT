"""
Optimized API Routes for GridBot
Following FastAPI best practices and .cursorrules
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio
import logging

from app.core.optimized_grid_manager import OptimizedGridManager, create_optimized_grid_manager
from app.services.telegram_alert import send_telegram_alert

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["optimized-grid"])

# Global grid manager instance
grid_manager: Optional[OptimizedGridManager] = None


# Pydantic models for API
class AssetUpdateRequest(BaseModel):
    """Request model for updating asset configuration"""
    min_price: Optional[float] = Field(None, gt=0)
    max_price: Optional[float] = Field(None, gt=0)
    grids: Optional[int] = Field(None, ge=2, le=20)
    quantity: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None


class TradingCycleRequest(BaseModel):
    """Request model for manual trading cycle"""
    symbols: Optional[List[str]] = Field(None, description="Specific symbols to trade")


class SystemStatusResponse(BaseModel):
    """Response model for system status"""
    status: str
    active_assets: int
    total_assets: int
    last_trading_cycle: Optional[str] = None
    uptime: str


# Dependency injection
async def get_grid_manager() -> OptimizedGridManager:
    """Dependency to get grid manager instance"""
    if grid_manager is None:
        raise HTTPException(status_code=503, detail="Grid manager not initialized")
    return grid_manager


# Health check endpoint
@router.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "optimized-grid-bot"}


# System status endpoint
@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get comprehensive system status"""
    try:
        active_assets = sum(1 for asset in manager.config.assets.values() if asset.is_active)
        total_assets = len(manager.config.assets)
        
        return SystemStatusResponse(
            status="operational",
            active_assets=active_assets,
            total_assets=total_assets,
            last_trading_cycle=manager.trading_history[-1].timestamp.isoformat() if manager.trading_history else None,
            uptime="running"
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving system status")


# Manual trading cycle endpoint
@router.post("/trading/cycle")
async def execute_trading_cycle(
    request: TradingCycleRequest,
    background_tasks: BackgroundTasks,
    manager: OptimizedGridManager = Depends(get_grid_manager)
):
    """Execute a manual trading cycle"""
    try:
        # Execute in background to avoid blocking
        background_tasks.add_task(manager.execute_grid_trading_cycle)
        
        return {
            "message": "Trading cycle initiated",
            "requested_symbols": request.symbols or "all"
        }
    except Exception as e:
        logger.error(f"Error executing trading cycle: {e}")
        raise HTTPException(status_code=500, detail="Error executing trading cycle")


# Get trading statistics
@router.get("/trading/statistics")
async def get_trading_statistics(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get comprehensive trading statistics"""
    try:
        stats = manager.get_trading_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting trading statistics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving trading statistics")


# Update asset configuration
@router.put("/assets/{symbol}")
async def update_asset_config(
    symbol: str,
    request: AssetUpdateRequest,
    manager: OptimizedGridManager = Depends(get_grid_manager)
):
    """Update configuration for a specific asset"""
    try:
        # Validate symbol exists
        if symbol not in manager.config.assets:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        
        # Prepare update data
        update_data = {}
        if request.min_price is not None:
            update_data["min_price"] = request.min_price
        if request.max_price is not None:
            update_data["max_price"] = request.max_price
        if request.grids is not None:
            update_data["grids"] = request.grids
        if request.quantity is not None:
            update_data["quantity"] = request.quantity
        if request.is_active is not None:
            update_data["is_active"] = request.is_active
        
        # Update configuration
        success = manager.update_asset_config(symbol, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update asset configuration")
        
        return {"message": f"Asset {symbol} configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating asset {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Error updating asset configuration")


# Get asset balances
@router.get("/assets/balances")
async def get_asset_balances(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get current asset balances"""
    try:
        balances = await manager.get_asset_balances()
        return {"balances": balances}
    except Exception as e:
        logger.error(f"Error getting balances: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving balances")


# Get current prices
@router.get("/assets/prices")
async def get_current_prices(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get current prices for all configured assets"""
    try:
        symbols = [asset.symbol for asset in manager.config.assets.values() if asset.is_active]
        prices = await manager.get_current_prices(symbols)
        return {"prices": prices}
    except Exception as e:
        logger.error(f"Error getting prices: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving prices")


# Save configuration
@router.post("/config/save")
async def save_configuration(
    filepath: str = "optimized_grid_config.json",
    manager: OptimizedGridManager = Depends(get_grid_manager)
):
    """Save current configuration to file"""
    try:
        success = manager.save_configuration(filepath)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
        
        return {"message": f"Configuration saved to {filepath}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise HTTPException(status_code=500, detail="Error saving configuration")


# Emergency stop endpoint
@router.post("/emergency/stop")
async def emergency_stop(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Emergency stop all trading activities"""
    try:
        # Deactivate all assets
        for asset in manager.config.assets.values():
            asset.is_active = False
        
        # Send emergency notification
        send_telegram_alert("🚨 EMERGENCY STOP ACTIVATED - All trading stopped")
        
        return {"message": "Emergency stop activated - All trading stopped"}
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        raise HTTPException(status_code=500, detail="Error executing emergency stop")


# Resume trading endpoint
@router.post("/emergency/resume")
async def resume_trading(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Resume trading activities"""
    try:
        # Reactivate all assets
        for asset in manager.config.assets.values():
            asset.is_active = True
        
        # Send resume notification
        send_telegram_alert("✅ TRADING RESUMED - All assets reactivated")
        
        return {"message": "Trading resumed - All assets reactivated"}
    except Exception as e:
        logger.error(f"Error resuming trading: {e}")
        raise HTTPException(status_code=500, detail="Error resuming trading")


# Initialize grid manager
async def initialize_grid_manager():
    """Initialize the grid manager with proper error handling"""
    global grid_manager
    config_file = "grid_config_optimized.json"
    
    try:
        grid_manager = await create_optimized_grid_manager(config_file)
        logger.info("Grid manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize grid manager: {e}")
        raise


# Startup event
@router.on_event("startup")
async def startup_event():
    """Application startup event to initialize the grid manager"""
    await initialize_grid_manager() 

@router.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event to close the grid manager"""
    if grid_manager:
        await grid_manager.close()
        logger.info("Grid manager closed successfully") 