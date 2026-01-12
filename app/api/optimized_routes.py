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
# from app.services.auto_rebalancer import auto_rebalancer  # Comentado temporalmente

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


class ConfigReloadRequest(BaseModel):
    """Request model for configuration reload"""
    config_file_path: Optional[str] = Field(None, description="Path to configuration file")


class RebalanceRequest(BaseModel):
    """Request model for rebalancing"""
    force: bool = Field(False, description="Force immediate rebalancing")


class RebalanceResponse(BaseModel):
    """Response model for rebalancing operations"""
    success: bool
    message: str
    results: List[Dict]
    total_transferred: float


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


# Configuration reload endpoint
@router.post("/config/reload")
async def reload_configuration(
    request: ConfigReloadRequest,
    manager: OptimizedGridManager = Depends(get_grid_manager)
):
    """Reload configuration from file"""
    try:
        config_file = request.config_file_path or "grid_config_optimized.json"
        
        success = await manager.reload_configuration(config_file)
        
        if success:
            return {
                "message": "Configuration reloaded successfully",
                "config_file": config_file,
                "status": "success"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reload configuration")
            
    except Exception as e:
        logger.error(f"Error reloading configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Error reloading configuration: {str(e)}")


# Rebalancer endpoints
# @router.post("/rebalancer/execute")
# async def execute_rebalance(request: RebalanceRequest = RebalanceRequest()):
#     """Execute rebalancing operation"""
#     try:
#         logger.info("🔄 Ejecutando rebalanceo manual")
#         
#         result = await auto_rebalancer.check_and_rebalance()
#         return result
#         
#     except Exception as e:
#         logger.error(f"Error ejecutando rebalanceo: {e}")
#         raise HTTPException(status_code=500, detail=f"Error ejecutando rebalanceo: {e}")


# @router.get("/rebalancer/status")
# async def get_rebalance_status():
#     """Get rebalancer status"""
#     try:
#         status = await auto_rebalancer.get_rebalance_status()
#         return status
#         
#     except Exception as e:
#         logger.error(f"Error obteniendo status de rebalanceo: {e}")
#         raise HTTPException(status_code=500, detail=f"Error obteniendo status: {e}")


# @router.post("/rebalancer/manual/{symbol}")
# async def manual_rebalance(symbol: str, usdt_amount: float):
#     """Execute manual rebalancing for a specific symbol"""
#     try:
#         logger.info(f"Ejecutando rebalanceo manual para {symbol}: ${usdt_amount}")
#         
#         result = await auto_rebalancer.manual_rebalance(symbol, usdt_amount)
#         return result
#         
#     except Exception as e:
#         logger.error(f"Error ejecutando rebalanceo manual para {symbol}: {e}")
#         raise HTTPException(status_code=500, detail=f"Error ejecutando rebalanceo manual: {e}")


# Grid manager restart endpoint
@router.post("/grid_manager/restart")
async def restart_grid_manager():
    """Restart the grid manager with current configuration"""
    global grid_manager
    
    try:
        # Get current config file path
        config_file = "grid_config_optimized.json"
        if grid_manager and grid_manager.config_file_path:
            config_file = grid_manager.config_file_path
        
        # Create new grid manager
        new_manager = await create_optimized_grid_manager(config_file)
        
        if new_manager:
            # Update global instance
            grid_manager = new_manager
            
            return {
                "message": "Grid manager restarted successfully",
                "config_file": config_file,
                "status": "success"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to restart grid manager")
            
    except Exception as e:
        logger.error(f"Error restarting grid manager: {e}")
        raise HTTPException(status_code=500, detail=f"Error restarting grid manager: {str(e)}")


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


# Trading statistics endpoint
@router.get("/trading/statistics")
async def get_trading_statistics(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get comprehensive trading statistics"""
    try:
        stats = manager.get_trading_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting trading statistics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving trading statistics")


# Asset configuration update endpoint
@router.put("/assets/{symbol}")
async def update_asset_config(
    symbol: str,
    request: AssetUpdateRequest,
    manager: OptimizedGridManager = Depends(get_grid_manager)
):
    """Update configuration for a specific asset"""
    try:
        # Convert request to dict, removing None values
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid update data provided")
        
        success = manager.update_asset_config(symbol, update_data)
        
        if success:
            return {
                "message": f"Configuration updated for {symbol}",
                "symbol": symbol,
                "updates": update_data
            }
        else:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
            
    except Exception as e:
        logger.error(f"Error updating asset config for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating asset configuration: {str(e)}")


# Asset balances endpoint
@router.get("/assets/balances")
async def get_asset_balances(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get current asset balances"""
    try:
        balances = await manager.get_asset_balances()
        return {"balances": balances}
    except Exception as e:
        logger.error(f"Error getting asset balances: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving asset balances")


# Current prices endpoint
@router.get("/assets/prices")
async def get_current_prices(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Get current prices for configured assets"""
    try:
        symbols = [asset.symbol for asset in manager.config.assets.values() if asset.is_active]
        prices = await manager.get_current_prices(symbols)
        return {"prices": prices}
    except Exception as e:
        logger.error(f"Error getting current prices: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving current prices")


# Configuration save endpoint
@router.post("/config/save")
async def save_configuration(
    filepath: str = "optimized_grid_config.json",
    manager: OptimizedGridManager = Depends(get_grid_manager)
):
    """Save current configuration to file"""
    try:
        success = await manager.save_configuration(filepath)
        
        if success:
            return {
                "message": "Configuration saved successfully",
                "filepath": filepath
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
            
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving configuration: {str(e)}")


# Emergency stop endpoint
@router.post("/emergency/stop")
async def emergency_stop(manager: OptimizedGridManager = Depends(get_grid_manager)):
    """Emergency stop all trading activities"""
    try:
        # Deactivate all assets
        for asset in manager.config.assets.values():
            asset.is_active = False
        
        # Send emergency notification
        send_telegram_alert("🚨 EMERGENCY STOP: All trading activities have been stopped!")
        
        return {
            "message": "Emergency stop executed",
            "status": "stopped",
            "active_assets": 0
        }
    except Exception as e:
        logger.error(f"Error executing emergency stop: {e}")
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
        send_telegram_alert("✅ TRADING RESUMED: All trading activities have been resumed!")
        
        active_assets = sum(1 for asset in manager.config.assets.values() if asset.is_active)
        
        return {
            "message": "Trading resumed",
            "status": "running",
            "active_assets": active_assets
        }
    except Exception as e:
        logger.error(f"Error resuming trading: {e}")
        raise HTTPException(status_code=500, detail="Error resuming trading")


# Initialize grid manager function
async def initialize_grid_manager():
    """Initialize the global grid manager instance"""
    global grid_manager
    
    try:
        config_file = "grid_config_optimized.json"
        grid_manager = await create_optimized_grid_manager(config_file)
        
        if grid_manager:
            logger.info("Grid manager initialized successfully")
        else:
            logger.error("Failed to initialize grid manager")
            
    except Exception as e:
        logger.error(f"Error initializing grid manager: {e}")


# Startup event
@router.on_event("startup")
async def startup_event():
    """Initialize grid manager on startup"""
    await initialize_grid_manager()


# Shutdown event
@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global grid_manager
    grid_manager = None 