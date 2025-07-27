#!/usr/bin/env python3
"""
Sistema de Gestión de Riesgos para Grid Trading Bot
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.services.binance_client import client as binance_client
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Niveles de riesgo"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskStatus(Enum):
    """Estados de riesgo"""
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    STOP_TRADING = "stop_trading"

@dataclass
class RiskMetrics:
    """Métricas de riesgo"""
    total_exposure: float
    max_daily_loss: float
    current_daily_loss: float
    largest_position: float
    portfolio_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    risk_score: float

@dataclass
class RiskAlert:
    """Alerta de riesgo"""
    level: RiskLevel
    message: str
    timestamp: datetime
    action_required: bool
    auto_resolved: bool = False

class RiskManager:
    """Gestor de riesgos para el Grid Trading Bot"""
    
    def __init__(self):
        # Configuración de límites de riesgo
        self.max_daily_loss_percentage = 0.05  # 5%
        self.max_position_size_percentage = 0.20  # 20%
        self.max_total_exposure_percentage = 0.80  # 80%
        self.stop_loss_percentage = 0.10  # 10%
        self.max_drawdown_percentage = 0.15  # 15%
        
        # Límites por activo
        self.max_asset_exposure = 0.30  # 30% por activo
        
        # Configuración de alertas
        self.alert_cooldown = timedelta(minutes=30)
        self.last_alerts: Dict[str, datetime] = {}
        
        # Estado del sistema
        self.trading_enabled = True
        self.emergency_stop = False
        
        logger.info("RiskManager inicializado con límites de riesgo configurados")
    
    async def check_portfolio_risk(self) -> RiskStatus:
        """Verifica el riesgo general del portafolio"""
        try:
            # Obtener métricas de riesgo
            risk_metrics = await self.calculate_risk_metrics()
            
            # Verificar límites críticos
            if risk_metrics.current_daily_loss >= self.max_daily_loss_percentage:
                await self._trigger_risk_alert(
                    RiskLevel.CRITICAL,
                    f"Pérdida diaria crítica: {risk_metrics.current_daily_loss:.2%}",
                    action_required=True
                )
                return RiskStatus.STOP_TRADING
            
            if risk_metrics.max_drawdown >= self.max_drawdown_percentage:
                await self._trigger_risk_alert(
                    RiskLevel.HIGH,
                    f"Drawdown máximo alcanzado: {risk_metrics.max_drawdown:.2%}",
                    action_required=True
                )
                return RiskStatus.DANGER
            
            if risk_metrics.total_exposure >= self.max_total_exposure_percentage:
                await self._trigger_risk_alert(
                    RiskLevel.MEDIUM,
                    f"Exposición total alta: {risk_metrics.total_exposure:.2%}",
                    action_required=False
                )
                return RiskStatus.WARNING
            
            # Verificar si hay alertas pendientes
            if self.emergency_stop:
                return RiskStatus.STOP_TRADING
            
            return RiskStatus.SAFE
            
        except Exception as e:
            logger.error(f"Error verificando riesgo del portafolio: {e}")
            await self._trigger_risk_alert(
                RiskLevel.HIGH,
                f"Error en verificación de riesgo: {str(e)}",
                action_required=True
            )
            return RiskStatus.DANGER
    
    async def check_asset_risk(self, symbol: str) -> RiskStatus:
        """Verifica el riesgo de un activo específico"""
        try:
            # Obtener posición del activo
            position = await self._get_asset_position(symbol)
            if not position:
                return RiskStatus.SAFE
            
            # Calcular exposición del activo
            total_portfolio_value = await self._get_total_portfolio_value()
            asset_exposure = position['value'] / total_portfolio_value
            
            # Verificar límites por activo
            if asset_exposure >= self.max_asset_exposure:
                await self._trigger_risk_alert(
                    RiskLevel.MEDIUM,
                    f"Exposición alta en {symbol}: {asset_exposure:.2%}",
                    action_required=False
                )
                return RiskStatus.WARNING
            
            # Verificar stop-loss
            if await self._check_stop_loss(symbol, position):
                await self._trigger_risk_alert(
                    RiskLevel.HIGH,
                    f"Stop-loss activado para {symbol}",
                    action_required=True
                )
                return RiskStatus.DANGER
            
            return RiskStatus.SAFE
            
        except Exception as e:
            logger.error(f"Error verificando riesgo del activo {symbol}: {e}")
            return RiskStatus.DANGER
    
    async def calculate_risk_metrics(self) -> RiskMetrics:
        """Calcula métricas de riesgo del portafolio"""
        try:
            # Obtener datos del portafolio
            account_info = await self._get_account_info()
            balances = account_info.get('balances', [])
            
            # Calcular exposición total
            total_exposure = 0.0
            total_value = 0.0
            largest_position = 0.0
            
            for balance in balances:
                if float(balance['free']) > 0 or float(balance['locked']) > 0:
                    asset = balance['asset']
                    if asset != 'USDT':
                        # Obtener precio del activo
                        try:
                            ticker = await self._get_symbol_ticker(f"{asset}USDT")
                            price = float(ticker['price'])
                            asset_value = (float(balance['free']) + float(balance['locked'])) * price
                            total_value += asset_value
                            largest_position = max(largest_position, asset_value)
                        except:
                            # Si no hay par USDT, usar valor nominal
                            asset_value = float(balance['free']) + float(balance['locked'])
                            total_value += asset_value
                            largest_position = max(largest_position, asset_value)
                    else:
                        usdt_value = float(balance['free']) + float(balance['locked'])
                        total_value += usdt_value
            
            # Calcular métricas
            total_exposure = (total_value - (await self._get_usdt_balance())) / total_value if total_value > 0 else 0.0
            largest_position_pct = largest_position / total_value if total_value > 0 else 0.0
            
            # Calcular pérdida diaria (simplificado)
            current_daily_loss = await self._calculate_daily_loss()
            
            # Calcular volatilidad (simplificado)
            portfolio_volatility = await self._calculate_portfolio_volatility()
            
            # Calcular Sharpe ratio (simplificado)
            sharpe_ratio = await self._calculate_sharpe_ratio()
            
            # Calcular máximo drawdown (simplificado)
            max_drawdown = await self._calculate_max_drawdown()
            
            # Calcular score de riesgo
            risk_score = self._calculate_risk_score(
                total_exposure, current_daily_loss, largest_position_pct,
                portfolio_volatility, max_drawdown
            )
            
            return RiskMetrics(
                total_exposure=total_exposure,
                max_daily_loss=self.max_daily_loss_percentage,
                current_daily_loss=current_daily_loss,
                largest_position=largest_position_pct,
                portfolio_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                risk_score=risk_score
            )
            
        except Exception as e:
            logger.error(f"Error calculando métricas de riesgo: {e}")
            # Retornar métricas por defecto en caso de error
            return RiskMetrics(
                total_exposure=0.0,
                max_daily_loss=self.max_daily_loss_percentage,
                current_daily_loss=0.0,
                largest_position=0.0,
                portfolio_volatility=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                risk_score=1.0
            )
    
    async def execute_stop_loss(self, symbol: str) -> bool:
        """Ejecuta stop-loss para un activo específico"""
        try:
            logger.info(f"Ejecutando stop-loss para {symbol}")
            
            # Obtener posición actual
            position = await self._get_asset_position(symbol)
            if not position or position['quantity'] <= 0:
                logger.info(f"No hay posición para vender en {symbol}")
                return False
            
            # Crear orden de venta de mercado
            order = await binance_client.create_order(
                symbol=f"{symbol}USDT",
                side='SELL',
                type='MARKET',
                quantity=position['quantity']
            )
            
            if order and order.get('status') == 'FILLED':
                await self._trigger_risk_alert(
                    RiskLevel.MEDIUM,
                    f"Stop-loss ejecutado para {symbol}: {position['quantity']} vendidos",
                    action_required=False
                )
                logger.info(f"Stop-loss ejecutado exitosamente para {symbol}")
                return True
            else:
                logger.error(f"Error ejecutando stop-loss para {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error ejecutando stop-loss para {symbol}: {e}")
            await self._trigger_risk_alert(
                RiskLevel.HIGH,
                f"Error ejecutando stop-loss para {symbol}: {str(e)}",
                action_required=True
            )
            return False
    
    async def set_emergency_stop(self, enabled: bool = True) -> None:
        """Activa/desactiva parada de emergencia"""
        self.emergency_stop = enabled
        self.trading_enabled = not enabled
        
        if enabled:
            await self._trigger_risk_alert(
                RiskLevel.CRITICAL,
                "🚨 PARADA DE EMERGENCIA ACTIVADA - Trading detenido",
                action_required=True
            )
            logger.warning("Parada de emergencia activada")
        else:
            await self._trigger_risk_alert(
                RiskLevel.LOW,
                "✅ Parada de emergencia desactivada - Trading reanudado",
                action_required=False
            )
            logger.info("Parada de emergencia desactivada")
    
    async def get_risk_status(self) -> Dict:
        """Obtiene el estado actual del sistema de riesgo"""
        try:
            risk_metrics = await self.calculate_risk_metrics()
            portfolio_status = await self.check_portfolio_risk()
            
            return {
                "status": portfolio_status.value,
                "trading_enabled": self.trading_enabled,
                "emergency_stop": self.emergency_stop,
                "metrics": {
                    "total_exposure": f"{risk_metrics.total_exposure:.2%}",
                    "current_daily_loss": f"{risk_metrics.current_daily_loss:.2%}",
                    "largest_position": f"{risk_metrics.largest_position:.2%}",
                    "portfolio_volatility": f"{risk_metrics.portfolio_volatility:.2%}",
                    "sharpe_ratio": f"{risk_metrics.sharpe_ratio:.2f}",
                    "max_drawdown": f"{risk_metrics.max_drawdown:.2%}",
                    "risk_score": f"{risk_metrics.risk_score:.2f}"
                },
                "limits": {
                    "max_daily_loss": f"{self.max_daily_loss_percentage:.2%}",
                    "max_position_size": f"{self.max_position_size_percentage:.2%}",
                    "max_total_exposure": f"{self.max_total_exposure_percentage:.2%}",
                    "stop_loss_percentage": f"{self.stop_loss_percentage:.2%}",
                    "max_drawdown": f"{self.max_drawdown_percentage:.2%}"
                },
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de riesgo: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }
    
    # Métodos auxiliares privados
    
    async def _trigger_risk_alert(self, level: RiskLevel, message: str, action_required: bool = False) -> None:
        """Envía alerta de riesgo"""
        try:
            alert_key = f"{level.value}_{message[:50]}"
            now = datetime.now()
            
            # Verificar cooldown de alertas
            if alert_key in self.last_alerts:
                time_diff = now - self.last_alerts[alert_key]
                if time_diff < self.alert_cooldown:
                    return
            
            self.last_alerts[alert_key] = now
            
            # Formatear mensaje
            emoji_map = {
                RiskLevel.LOW: "🟢",
                RiskLevel.MEDIUM: "🟡",
                RiskLevel.HIGH: "🟠",
                RiskLevel.CRITICAL: "🔴"
            }
            
            formatted_message = f"{emoji_map.get(level, '⚪')} **ALERTA DE RIESGO** ({level.value.upper()})\n\n{message}\n\n"
            if action_required:
                formatted_message += "⚠️ **ACCIÓN REQUERIDA**"
            
            # Enviar por Telegram
            await send_telegram_alert(formatted_message)
            
            logger.warning(f"Alerta de riesgo enviada: {level.value} - {message}")
            
        except Exception as e:
            logger.error(f"Error enviando alerta de riesgo: {e}")
    
    async def _get_account_info(self) -> Dict:
        """Obtiene información de la cuenta"""
        try:
            return await binance_client.get_account()
        except Exception as e:
            logger.error(f"Error obteniendo información de cuenta: {e}")
            return {"balances": []}
    
    async def _get_symbol_ticker(self, symbol: str) -> Dict:
        """Obtiene ticker de un símbolo"""
        try:
            return await binance_client.get_symbol_ticker(symbol=symbol)
        except Exception as e:
            logger.error(f"Error obteniendo ticker de {symbol}: {e}")
            return {"price": "0"}
    
    async def _get_usdt_balance(self) -> float:
        """Obtiene balance de USDT"""
        try:
            account_info = await self._get_account_info()
            for balance in account_info.get('balances', []):
                if balance['asset'] == 'USDT':
                    return float(balance['free']) + float(balance['locked'])
            return 0.0
        except Exception as e:
            logger.error(f"Error obteniendo balance USDT: {e}")
            return 0.0
    
    async def _get_asset_position(self, symbol: str) -> Optional[Dict]:
        """Obtiene posición de un activo"""
        try:
            account_info = await self._get_account_info()
            for balance in account_info.get('balances', []):
                if balance['asset'] == symbol:
                    quantity = float(balance['free']) + float(balance['locked'])
                    if quantity > 0:
                        ticker = await self._get_symbol_ticker(f"{symbol}USDT")
                        price = float(ticker['price'])
                        return {
                            'symbol': symbol,
                            'quantity': quantity,
                            'price': price,
                            'value': quantity * price
                        }
            return None
        except Exception as e:
            logger.error(f"Error obteniendo posición de {symbol}: {e}")
            return None
    
    async def _get_total_portfolio_value(self) -> float:
        """Obtiene valor total del portafolio"""
        try:
            account_info = await self._get_account_info()
            total_value = 0.0
            
            for balance in account_info.get('balances', []):
                if float(balance['free']) > 0 or float(balance['locked']) > 0:
                    asset = balance['asset']
                    if asset == 'USDT':
                        total_value += float(balance['free']) + float(balance['locked'])
                    else:
                        try:
                            ticker = await self._get_symbol_ticker(f"{asset}USDT")
                            price = float(ticker['price'])
                            asset_value = (float(balance['free']) + float(balance['locked'])) * price
                            total_value += asset_value
                        except:
                            # Si no hay par USDT, usar valor nominal
                            asset_value = float(balance['free']) + float(balance['locked'])
                            total_value += asset_value
            
            return total_value
        except Exception as e:
            logger.error(f"Error calculando valor total del portafolio: {e}")
            return 0.0
    
    async def _check_stop_loss(self, symbol: str, position: Dict) -> bool:
        """Verifica si se debe activar stop-loss"""
        # Implementación simplificada - en producción se usarían datos históricos
        try:
            # Obtener precio actual
            ticker = await self._get_symbol_ticker(f"{symbol}USDT")
            current_price = float(ticker['price'])
            
            # Calcular pérdida (simplificado - asumiendo precio de entrada)
            # En producción se usaría el precio promedio de entrada
            entry_price = position['price']  # Simplificado
            loss_percentage = (entry_price - current_price) / entry_price
            
            return loss_percentage >= self.stop_loss_percentage
            
        except Exception as e:
            logger.error(f"Error verificando stop-loss para {symbol}: {e}")
            return False
    
    async def _calculate_daily_loss(self) -> float:
        """Calcula pérdida diaria (simplificado)"""
        # Implementación simplificada - en producción se usarían datos históricos
        return 0.0
    
    async def _calculate_portfolio_volatility(self) -> float:
        """Calcula volatilidad del portafolio (simplificado)"""
        # Implementación simplificada - en producción se usarían datos históricos
        return 0.05  # 5% por defecto
    
    async def _calculate_sharpe_ratio(self) -> float:
        """Calcula Sharpe ratio (simplificado)"""
        # Implementación simplificada - en producción se usarían datos históricos
        return 1.0  # 1.0 por defecto
    
    async def _calculate_max_drawdown(self) -> float:
        """Calcula máximo drawdown (simplificado)"""
        # Implementación simplificada - en producción se usarían datos históricos
        return 0.05  # 5% por defecto
    
    def _calculate_risk_score(self, total_exposure: float, daily_loss: float, 
                            largest_position: float, volatility: float, 
                            max_drawdown: float) -> float:
        """Calcula score de riesgo (0-1, donde 1 es máximo riesgo)"""
        # Fórmula simplificada para calcular score de riesgo
        exposure_score = min(total_exposure / self.max_total_exposure_percentage, 1.0)
        loss_score = min(daily_loss / self.max_daily_loss_percentage, 1.0)
        position_score = min(largest_position / self.max_position_size_percentage, 1.0)
        drawdown_score = min(max_drawdown / self.max_drawdown_percentage, 1.0)
        
        # Ponderación de factores
        risk_score = (
            exposure_score * 0.3 +
            loss_score * 0.3 +
            position_score * 0.2 +
            drawdown_score * 0.2
        )
        
        return min(risk_score, 1.0)

# Instancia global del RiskManager
risk_manager = RiskManager() 