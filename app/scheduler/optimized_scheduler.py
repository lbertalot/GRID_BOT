"""
Optimized Scheduler for GridBot
Integrating all created scripts with best practices
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.optimized_grid_manager import OptimizedGridManager, create_optimized_grid_manager
from app.services.telegram_alert import send_telegram_alert
from app.services.min_qty_updater import update_min_qty_in_db_and_config, create_asset_min_qty_table

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizedGridScheduler:
    """
    Optimized scheduler following functional programming principles
    and integrating all created scripts
    """
    
    def __init__(self, config_file: str = "grid_config_optimized.json"):
        self.config_file = config_file
        self.grid_manager: Optional[OptimizedGridManager] = None
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime] = None
        
    async def initialize(self) -> bool:
        """Initialize the scheduler and grid manager"""
        try:
            # Crear tabla de cantidades mínimas si no existe
            await create_asset_min_qty_table()
            # Create grid manager
            self.grid_manager = await create_optimized_grid_manager(self.config_file)
            
            # Configure scheduler
            self.scheduler.add_job(
                self._execute_trading_cycle,
                IntervalTrigger(seconds=60),
                id="grid_trading_cycle",
                name="Grid Trading Cycle",
                replace_existing=True
            )
            
            # Add monitoring job
            self.scheduler.add_job(
                self._monitor_system_health,
                IntervalTrigger(minutes=5),
                id="system_health_monitor",
                name="System Health Monitor",
                replace_existing=True
            )
            
            # Add performance analysis job
            self.scheduler.add_job(
                self._analyze_performance,
                IntervalTrigger(hours=1),
                id="performance_analysis",
                name="Performance Analysis",
                replace_existing=True
            )
            
            # Add daily min_qty update job
            self.scheduler.add_job(
                lambda: asyncio.create_task(update_min_qty_in_db_and_config()),
                IntervalTrigger(days=1),
                id="update_min_qty_daily",
                name="Actualizar cantidades mínimas diariamente",
                replace_existing=True
            )
            
            logger.info("Optimized scheduler initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the scheduler"""
        try:
            if not self.grid_manager:
                await self.initialize()
            
            self.scheduler.start()
            self.is_running = True
            
            # Send startup notification
            await self._send_startup_notification()
            
            logger.info("Optimized scheduler started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown()
            self.is_running = False
            
            # Send shutdown notification
            await self._send_shutdown_notification()
            
            logger.info("Optimized scheduler stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            return False
    
    async def _execute_trading_cycle(self):
        """Execute a complete trading cycle"""
        try:
            if not self.grid_manager:
                logger.error("Grid manager not initialized")
                return
            
            self.cycle_count += 1
            self.last_cycle_time = datetime.now()
            
            # Execute trading cycle
            results = await self.grid_manager.execute_grid_trading_cycle()
            
            # Log results
            if results:
                logger.info(f"Trading cycle {self.cycle_count}: {len(results)} trades executed")
                await self._log_trading_results(results)
            else:
                logger.info(f"Trading cycle {self.cycle_count}: No trades executed")
                
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            await self._send_error_notification(f"Trading cycle error: {e}")
    
    async def _monitor_system_health(self):
        """Monitor system health and performance"""
        try:
            if not self.grid_manager:
                return
            
            # Get system status
            balances = await self.grid_manager.get_asset_balances()
            symbols = [asset.symbol for asset in self.grid_manager.config.assets.values() if asset.is_active]
            prices = await self.grid_manager.get_current_prices(symbols)
            
            # Check for issues
            issues = []
            
            # Check if balances are sufficient
            for symbol, asset_config in self.grid_manager.config.assets.items():
                if not asset_config.is_active:
                    continue
                    
                base_asset = symbol.replace("USDT", "")
                balance = balances.get(base_asset, 0)
                
                if balance < asset_config.quantity:
                    issues.append(f"Insufficient balance for {symbol}: {balance} < {asset_config.quantity}")
            
            # Send health report if issues found
            if issues:
                await self._send_health_alert(issues)
            else:
                logger.info("System health check passed")
                
        except Exception as e:
            logger.error(f"Error in health monitoring: {e}")
    
    async def _analyze_performance(self):
        """Analyze trading performance and generate reports"""
        try:
            if not self.grid_manager:
                return
            
            # Get trading statistics
            stats = self.grid_manager.get_trading_statistics()
            
            # Generate performance report
            report = await self._generate_performance_report(stats)
            
            # Send performance report
            await self._send_performance_report(report)
            
        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")
    
    async def _log_trading_results(self, results: List):
        """Log trading results for analysis"""
        try:
            # Save to trading history file
            history_file = "trading_history.json"
            
            # Load existing history
            existing_history = []
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    existing_history = json.load(f)
            
            # Add new results
            for result in results:
                existing_history.append({
                    "timestamp": result.timestamp.isoformat(),
                    "symbol": result.symbol,
                    "action": result.action,
                    "quantity": result.quantity,
                    "price": result.price,
                    "order_id": result.order_id,
                    "status": result.status,
                    "profit": result.profit
                })
            
            # Save updated history
            with open(history_file, 'w') as f:
                json.dump(existing_history, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error logging trading results: {e}")
    
    async def _generate_performance_report(self, stats: Dict) -> Dict:
        """Generate comprehensive performance report"""
        try:
            total_trades = stats.get("total_trades", 0)
            total_profit = stats.get("total_profit", 0)
            asset_stats = stats.get("asset_statistics", {})
            
            # Calculate metrics
            avg_profit_per_trade = total_profit / total_trades if total_trades > 0 else 0
            profitable_assets = sum(1 for asset_data in asset_stats.values() if asset_data.get("profit", 0) > 0)
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_trades": total_trades,
                "total_profit": total_profit,
                "avg_profit_per_trade": avg_profit_per_trade,
                "profitable_assets": profitable_assets,
                "total_assets": len(asset_stats),
                "asset_performance": asset_stats,
                "cycle_count": self.cycle_count,
                "uptime": self._calculate_uptime()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {"error": str(e)}
    
    def _calculate_uptime(self) -> str:
        """Calculate system uptime"""
        if not self.last_cycle_time:
            return "Unknown"
        
        uptime = datetime.now() - self.last_cycle_time
        return str(uptime)
    
    async def _send_startup_notification(self):
        """Send startup notification"""
        try:
            message = (
                "🚀 Optimized GridBot Started\n\n"
                f"📊 Assets configured: {len(self.grid_manager.config.assets)}\n"
                f"⏰ Update interval: {self.grid_manager.config.update_interval}s\n"
                f"💰 Min notional: ${self.grid_manager.config.min_notional_threshold}\n\n"
                "✅ System ready for trading!"
            )
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error sending startup notification: {e}")
    
    async def _send_shutdown_notification(self):
        """Send shutdown notification"""
        try:
            message = (
                "🛑 Optimized GridBot Stopped\n\n"
                f"📊 Total cycles: {self.cycle_count}\n"
                f"⏰ Last cycle: {self.last_cycle_time.isoformat() if self.last_cycle_time else 'N/A'}\n\n"
                "System shutdown complete"
            )
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error sending shutdown notification: {e}")
    
    async def _send_error_notification(self, error_message: str):
        """Send error notification"""
        try:
            message = f"❌ GridBot Error\n\n{error_message}\n\nSystem continuing operation..."
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    async def _send_health_alert(self, issues: List[str]):
        """Send health alert"""
        try:
            message = "⚠️ System Health Alert\n\n"
            for issue in issues:
                message += f"• {issue}\n"
            message += "\nPlease check system configuration"
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error sending health alert: {e}")
    
    async def _send_performance_report(self, report: Dict):
        """Send performance report"""
        try:
            message = (
                "📊 Performance Report\n\n"
                f"📈 Total trades: {report.get('total_trades', 0)}\n"
                f"💰 Total profit: ${report.get('total_profit', 0):.4f}\n"
                f"📊 Avg profit/trade: ${report.get('avg_profit_per_trade', 0):.4f}\n"
                f"✅ Profitable assets: {report.get('profitable_assets', 0)}/{report.get('total_assets', 0)}\n"
                f"🔄 Cycles completed: {report.get('cycle_count', 0)}\n"
                f"⏰ Uptime: {report.get('uptime', 'Unknown')}"
            )
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error sending performance report: {e}")
    
    def get_status(self) -> Dict:
        """Get current scheduler status"""
        return {
            "is_running": self.is_running,
            "cycle_count": self.cycle_count,
            "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            "jobs": [job.id for job in self.scheduler.get_jobs()],
            "grid_manager_initialized": self.grid_manager is not None
        }


# Global scheduler instance
optimized_scheduler: Optional[OptimizedGridScheduler] = None


async def initialize_optimized_scheduler() -> OptimizedGridScheduler:
    """Initialize and return the optimized scheduler"""
    global optimized_scheduler
    
    if optimized_scheduler is None:
        optimized_scheduler = OptimizedGridScheduler()
        await optimized_scheduler.initialize()
    
    return optimized_scheduler


async def start_optimized_scheduler() -> bool:
    """Start the optimized scheduler"""
    scheduler = await initialize_optimized_scheduler()
    return await scheduler.start()


async def stop_optimized_scheduler() -> bool:
    """Stop the optimized scheduler"""
    global optimized_scheduler
    
    if optimized_scheduler:
        return await optimized_scheduler.stop()
    
    return True 