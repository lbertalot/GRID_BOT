"""
Servicio para mantener las métricas actualizadas automáticamente
"""

import asyncio
import logging
from datetime import datetime
from app.core.metrics import trading_metrics
from app.services.binance_service import get_binance_client

logger = logging.getLogger(__name__)

class MetricsUpdater:
    """
    Servicio para actualizar métricas automáticamente
    """
    
    def __init__(self):
        self.update_interval = 30  # segundos
        self.is_running = False
        
    async def start(self):
        """Iniciar el actualizador de métricas"""
        self.is_running = True
        logger.info("🚀 Iniciando actualizador de métricas")
        
        while self.is_running:
            try:
                await self.update_metrics()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error actualizando métricas: {e}")
                await asyncio.sleep(10)  # Esperar menos tiempo en caso de error
    
    async def stop(self):
        """Detener el actualizador de métricas"""
        self.is_running = False
        logger.info("🛑 Deteniendo actualizador de métricas")
    
    async def update_metrics(self):
        """Actualizar todas las métricas"""
        try:
            # Obtener balance real de Binance
            from app.services.binance_client_singleton import binance_client_singleton
            
            try:
                account_info = binance_client_singleton.get_account_info()
            except Exception as e:
                logger.warning(f"No se pudo obtener información de cuenta: {e}")
                return
            portfolio_value = 0.0
            balances = {}
            
            # Procesar balances
            for bal in account_info['balances']:
                asset = bal['asset']
                free = float(bal['free'])
                locked = float(bal['locked'])
                
                if free > 0 or locked > 0:
                    balances[asset] = free + locked
                    
                    # Calcular valor en USDT para activos principales
                    if asset in ['BTC', 'ETH', 'USDT', 'SPK']:
                        try:
                            if asset == 'USDT':
                                portfolio_value += free + locked
                            else:
                                # Obtener precio en USDT
                                price = binance_client_singleton.get_symbol_price(f"{asset}USDT")
                                portfolio_value += (free + locked) * price
                        except Exception as e:
                            logger.warning(f"No se pudo obtener precio para {asset}: {e}")
            
            # Actualizar métricas
            trading_metrics.update_profit_metrics(
                total_profit=0.0,  # Se actualizará cuando haya trades
                portfolio_value=portfolio_value,
                strategy="grid"
            )
            
            trading_metrics.update_bot_status(
                is_active=True,  # Asumiendo que está activo
                strategy="grid"
            )
            
            # Actualizar balances solo para activos principales
            main_balances = {}
            for asset in ['USDT', 'BTC', 'ETH', 'SPK']:
                if asset in balances:
                    main_balances[asset] = balances[asset]
            
            trading_metrics.update_balances(main_balances, "grid")
            
            logger.info(f"✅ Métricas actualizadas - Portfolio: {portfolio_value:.2f} USDT")
            
        except Exception as e:
            logger.error(f"Error actualizando métricas: {e}")

# Instancia global
metrics_updater = MetricsUpdater()

async def start_metrics_updater():
    """Función para iniciar el actualizador de métricas"""
    await metrics_updater.start()

async def stop_metrics_updater():
    """Función para detener el actualizador de métricas"""
    await metrics_updater.stop() 