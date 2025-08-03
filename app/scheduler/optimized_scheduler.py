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
import requests

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.optimized_grid_manager import OptimizedGridManager, create_optimized_grid_manager
from app.services.telegram_alert import send_telegram_alert, send_telegram_alert_async
from app.services.min_qty_updater import update_min_qty_in_db_and_config, create_asset_min_qty_table
from app.services.auto_rebalancer import auto_rebalancer

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
        self.balance_history = {}
        self.last_balance_report_time: Optional[datetime] = None
        
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
            
            # Add balance monitoring job (cada hora)
            self.scheduler.add_job(
                self._monitor_balances_hourly,
                IntervalTrigger(hours=1),
                id="balance_monitor_hourly",
                name="Balance Monitor Hourly",
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
            
            # Add auto rebalancer job (cada hora)
            self.scheduler.add_job(
                self._auto_rebalance_cycle,
                IntervalTrigger(hours=1),
                id="auto_rebalance_cycle",
                name="Auto Rebalance Cycle",
                replace_existing=True
            )
            
            logger.info("Optimized scheduler initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            return False

    async def _monitor_balances_hourly(self):
        """Monitorea balances cada hora y envía reporte por Telegram"""
        try:
            logger.info("🕐 Iniciando monitoreo de balances horario...")
            
            # Obtener balances actuales
            balances = await self._obtener_balances_actuales()
            precios = await self._obtener_precios_actuales()
            config = await self._obtener_configuracion_actual()
            
            # Calcular valores
            valor_total_usdt, balances_con_valor = self._calcular_valor_total_balances(balances, precios)
            activos_operativos, activos_sin_saldo = self._analizar_activos_operativos(balances, precios, config)
            
            # Calcular cambio desde el último reporte
            cambio_porcentual = 0
            cambio_usdt = 0
            
            if self.last_balance_report_time and valor_total_usdt in self.balance_history:
                valor_anterior = self.balance_history[valor_total_usdt]
                cambio_usdt = valor_total_usdt - valor_anterior
                cambio_porcentual = self._calcular_cambio_porcentual(valor_total_usdt, valor_anterior)
            
            # Guardar valor actual
            self.balance_history[datetime.now()] = valor_total_usdt
            self.last_balance_report_time = datetime.now()
            
            # Generar y enviar reporte por Telegram
            mensaje = self._generar_mensaje_balance_report(
                valor_total_usdt, cambio_usdt, cambio_porcentual,
                activos_operativos, activos_sin_saldo
            )
            
            send_telegram_alert(mensaje)
            
            logger.info(f"✅ Reporte de balances enviado - Valor total: ${valor_total_usdt:.2f} USDT")
            
        except Exception as e:
            logger.error(f"❌ Error en monitoreo de balances: {e}")
            self._send_error_notification(f"Error en monitoreo de balances: {e}")

    async def _auto_rebalance_cycle(self):
        """Ejecuta ciclo de rebalanceo automático"""
        try:
            logger.info("🔄 Iniciando ciclo de rebalanceo automático")
            
            # Ejecutar rebalanceo
            result = await auto_rebalancer.check_and_rebalance()
            
            if result["status"] == "success":
                rebalance_results = result.get("rebalance_results", [])
                successful_rebalances = len([r for r in rebalance_results if r.get("status") == "success"])
                failed_rebalances = len([r for r in rebalance_results if r.get("status") != "success"])
                
                if successful_rebalances > 0:
                    total_usdt_spent = sum(r.get("usdt_spent", 0) for r in rebalance_results if r.get("status") == "success")
                    mensaje = f"🔄 Rebalanceo Automático Completado\n\n"
                    mensaje += f"✅ Rebalanceos exitosos: {successful_rebalances}\n"
                    mensaje += f"❌ Rebalanceos fallidos: {failed_rebalances}\n"
                    mensaje += f"💰 Total invertido: ${total_usdt_spent:.2f} USDT\n\n"
                    
                    # Detalles de activos rebalanceados
                    for rebalance_result in rebalance_results:
                        symbol = rebalance_result.get("symbol", "Unknown")
                        status = rebalance_result.get("status", "unknown")
                        if status == "success":
                            usdt_spent = rebalance_result.get("usdt_spent", 0)
                            mensaje += f"✅ {symbol}: +${usdt_spent:.2f}\n"
                        else:
                            reason = rebalance_result.get("reason", "Error desconocido")
                            mensaje += f"❌ {symbol}: {reason}\n"
                    
                    send_telegram_alert(mensaje)
                    logger.info(f"✅ Rebalanceo completado: {successful_rebalances} exitosos, {failed_rebalances} fallidos")
                else:
                    logger.info("ℹ️ No se requirió rebalanceo o no hay USDT disponible")
            elif result["status"] == "skipped":
                logger.info("ℹ️ Rebalanceo saltado: ya en progreso")
            else:
                logger.error(f"❌ Error en rebalanceo: {result.get('message', 'Error desconocido')}")
                self._send_error_notification(f"Error en rebalanceo automático: {result.get('message', 'Error desconocido')}")
            
        except Exception as e:
            logger.error(f"❌ Error en ciclo de rebalanceo: {e}")
            self._send_error_notification(f"Error en rebalanceo automático: {e}")

    async def _obtener_balances_actuales(self) -> Dict:
        """Obtiene los balances actuales del sistema"""
        try:
            if self.grid_manager:
                return await self.grid_manager.get_asset_balances()
            else:
                return {}
        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return {}

    async def _obtener_precios_actuales(self) -> Dict:
        """Obtiene los precios actuales de los activos"""
        activos = [
            "BNBUSDT", "ANIMEUSDT", "GPSUSDT", "GUNUSDT", 
            "SIGNUSDT", "SPKUSDT", "HOMEUSDT", "HUMAUSDT"
        ]
        
        precios = {}
        for activo in activos:
            try:
                response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={activo}")
                if response.status_code == 200:
                    data = response.json()
                    precios[activo] = float(data['price'])
                else:
                    precios[activo] = 0
            except Exception as e:
                logger.error(f"Error obteniendo precio de {activo}: {e}")
                precios[activo] = 0
        
        return precios

    async def _obtener_configuracion_actual(self) -> Dict:
        """Obtiene la configuración actual del sistema"""
        try:
            response = requests.get("http://localhost:8000/api/trade/grid_config")
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception as e:
            logger.error(f"Error obteniendo configuración: {e}")
            return {}

    def _calcular_valor_total_balances(self, balances: Dict, precios: Dict) -> tuple:
        """Calcula el valor total en USDT de todos los balances"""
        valor_total_usdt = 0
        balances_con_valor = {}
        
        for asset, balance in balances.items():
            if balance > 0:
                if asset == "USDT":
                    valor_usdt = balance
                    balances_con_valor[asset] = {
                        "balance": balance,
                        "valor_usdt": valor_usdt,
                        "precio": 1.0
                    }
                    valor_total_usdt += valor_usdt
                else:
                    symbol = f"{asset}USDT"
                    if symbol in precios:
                        precio = precios[symbol]
                        valor_usdt = balance * precio
                        balances_con_valor[asset] = {
                            "balance": balance,
                            "valor_usdt": valor_usdt,
                            "precio": precio
                        }
                        valor_total_usdt += valor_usdt
        
        return valor_total_usdt, balances_con_valor

    def _analizar_activos_operativos(self, balances: Dict, precios: Dict, config: Dict) -> tuple:
        """Analiza qué activos están operativos"""
        activos_configurados = ["BNBUSDT", "ANIMEUSDT", "GPSUSDT", "GUNUSDT", 
                               "SIGNUSDT", "SPKUSDT", "HOMEUSDT", "HUMAUSDT"]
        
        activos_operativos = []
        activos_sin_saldo = []
        
        for activo in activos_configurados:
            base_asset = activo.replace("USDT", "")
            balance = balances.get(base_asset, 0)
            
            cantidad_requerida = 0
            if activo in config:
                cantidad_requerida = config[activo].get('quantity', 0)
            
            if balance >= cantidad_requerida and cantidad_requerida > 0:
                activos_operativos.append(activo)
            else:
                activos_sin_saldo.append(activo)
        
        return activos_operativos, activos_sin_saldo

    def _calcular_cambio_porcentual(self, valor_actual: float, valor_anterior: float) -> float:
        """Calcula el cambio porcentual entre dos valores"""
        if valor_anterior == 0:
            return 0
        return ((valor_actual - valor_anterior) / valor_anterior) * 100

    def _generar_mensaje_balance_report(self, valor_total: float, cambio_usdt: float, 
                                       cambio_porcentual: float, activos_operativos: List[str], 
                                       activos_sin_saldo: List[str]) -> str:
        """Genera el mensaje para el reporte de balances"""
        
        # Emoji para el cambio
        if cambio_porcentual > 0:
            cambio_emoji = "📈"
            cambio_texto = "GANANCIA"
        elif cambio_porcentual < 0:
            cambio_emoji = "📉"
            cambio_texto = "PÉRDIDA"
        else:
            cambio_emoji = "➡️"
            cambio_texto = "SIN CAMBIO"
        
        mensaje = f"""
🕐 <b>REPORTE HORARIO GRIDBOT</b>
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💰 <b>VALOR TOTAL:</b> ${valor_total:.2f} USDT

{cambio_emoji} <b>{cambio_texto}:</b> ${cambio_usdt:.2f} ({cambio_porcentual:.2f}%)

📊 <b>ACTIVOS OPERATIVOS:</b> {len(activos_operativos)}/8
✅ {', '.join(activos_operativos) if activos_operativos else 'Ninguno'}

❌ <b>ACTIVOS SIN SALDO:</b> {len(activos_sin_saldo)}/8
🔴 {', '.join(activos_sin_saldo) if activos_sin_saldo else 'Ninguno'}

💡 <b>POTENCIAL DIARIO:</b> ~${len(activos_operativos) * 10:.2f}
🎯 <b>POTENCIAL MÁXIMO:</b> ~$80.00/día

🤖 <b>Estado:</b> {'🟢 OPERATIVO' if activos_operativos else '🔴 INACTIVO'}
        """
        
        return mensaje.strip()
    
    async def start(self) -> bool:
        """Start the scheduler"""
        try:
            if not self.grid_manager:
                await self.initialize()
            
            self.scheduler.start()
            self.is_running = True
            
            # Send startup notification
            self._send_startup_notification()
            
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
            self._send_shutdown_notification()
            
            logger.info("Optimized scheduler stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            return False

    async def _execute_trading_cycle(self):
        """Execute a trading cycle"""
        try:
            if not self.grid_manager:
                logger.error("Grid manager not initialized")
                return
            
            self.cycle_count += 1
            self.last_cycle_time = datetime.now()
            
            # Execute trading cycle
            results = await self.grid_manager.execute_grid_trading_cycle()
            
            # Log results
            self._log_trading_results(results)
            
            logger.info(f"Trading cycle {self.cycle_count}: {len(results)} trades executed")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            self._send_error_notification(f"Error in trading cycle: {e}")

    async def _monitor_system_health(self):
        """Monitor system health and send alerts"""
        try:
            issues = []
            
            # Check if grid manager is running
            if not self.grid_manager:
                issues.append("Grid manager not initialized")
            
            # Check if trading cycles are running
            if self.last_cycle_time:
                time_since_last_cycle = datetime.now() - self.last_cycle_time
                if time_since_last_cycle.total_seconds() > 300:  # 5 minutes
                    issues.append(f"No trading cycles for {time_since_last_cycle.total_seconds()/60:.1f} minutes")
            
            # Send health alert if issues found
            if issues:
                self._send_health_alert(issues)
            else:
                logger.info("System health check passed")
                
        except Exception as e:
            logger.error(f"Error in health monitoring: {e}")

    async def _analyze_performance(self):
        """Analyze system performance and send report"""
        try:
            if not self.grid_manager:
                return
            
            # Get trading statistics
            stats = self.grid_manager.get_trading_statistics()
            
            # Generate performance report
            report = self._generate_performance_report(stats)
            
            # Send performance report
            self._send_performance_report(report)
            
        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")

    def _log_trading_results(self, results: List):
        """Log trading results"""
        if not results:
            return
        
        for result in results:
            logger.info(f"Trade executed: {result.action} {result.quantity} {result.symbol} at ${result.price:.6f}")

    def _generate_performance_report(self, stats: Dict) -> Dict:
        """Generate performance report"""
        uptime = self._calculate_uptime()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "uptime": uptime,
            "cycle_count": self.cycle_count,
            "trading_stats": stats,
            "system_status": "operational" if self.is_running else "stopped"
        }
        
        return report

    def _calculate_uptime(self) -> str:
        """Calculate system uptime"""
        if not self.last_cycle_time:
            return "Unknown"
        
        uptime = datetime.now() - self.last_cycle_time
        return str(uptime)

    def _send_startup_notification(self):
        """Send startup notification"""
        try:
            message = f"""🚀 Optimized GridBot Started

📊 Assets configured: {len(self.grid_manager.config.assets) if self.grid_manager else 0}
⏰ Update interval: 60s
💰 Min notional: $10.0

✅ System ready for trading!"""
            
            send_telegram_alert(message)
            
        except Exception as e:
            logger.error(f"Error sending startup notification: {e}")

    def _send_shutdown_notification(self):
        """Send shutdown notification"""
        try:
            message = f"""🛑 GridBot Shutdown

📊 Total cycles: {self.cycle_count}
⏰ Last cycle: {self.last_cycle_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_cycle_time else 'N/A'}

🔴 System stopped"""
            
            send_telegram_alert(message)
            
        except Exception as e:
            logger.error(f"Error sending shutdown notification: {e}")

    def _send_error_notification(self, error_message: str):
        """Send error notification"""
        try:
            message = f"""❌ GridBot Error

🔍 Error: {error_message}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ Please check system logs"""
            
            send_telegram_alert(message)
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")

    def _send_health_alert(self, issues: List[str]):
        """Send health alert"""
        try:
            message = f"""⚠️ GridBot Health Alert

🔍 Issues detected:
"""
            for issue in issues:
                message += f"• {issue}\n"
            
            message += f"""
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 Please investigate"""
            
            send_telegram_alert(message)
            
        except Exception as e:
            logger.error(f"Error sending health alert: {e}")

    def _send_performance_report(self, report: Dict):
        """Send performance report"""
        try:
            stats = report.get("trading_stats", {})
            
            if "message" in stats and stats["message"] == "No trading history available":
                return  # Don't send report if no trading history
            
            total_trades = stats.get("total_trades", 0)
            total_profit = stats.get("total_profit", 0)
            
            message = f"""📊 Performance Report

📈 Total trades: {total_trades}
💵 Total profit: ${total_profit:.2f}
⏰ Uptime: {report.get("uptime", "Unknown")}
🔄 Cycles: {report.get("cycle_count", 0)}

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            send_telegram_alert(message)
            
        except Exception as e:
            logger.error(f"Error sending performance report: {e}")

    def get_status(self) -> Dict:
        """Get scheduler status"""
        return {
            "is_running": self.is_running,
            "cycle_count": self.cycle_count,
            "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            "uptime": self._calculate_uptime(),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }


# Global scheduler instance
_scheduler_instance: Optional[OptimizedGridScheduler] = None


async def initialize_optimized_scheduler() -> OptimizedGridScheduler:
    """Initialize the optimized scheduler"""
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = OptimizedGridScheduler()
        await _scheduler_instance.initialize()
    
    return _scheduler_instance


async def start_optimized_scheduler() -> bool:
    """Start the optimized scheduler"""
    scheduler = await initialize_optimized_scheduler()
    return await scheduler.start()


async def stop_optimized_scheduler() -> bool:
    """Stop the optimized scheduler"""
    global _scheduler_instance
    
    if _scheduler_instance:
        return await _scheduler_instance.stop()
    
    return True 