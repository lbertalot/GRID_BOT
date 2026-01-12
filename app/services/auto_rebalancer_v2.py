"""
AutoRebalancer V2 - Sistema de liquidez autónoma para GridBot v2.5

Este servicio refactorizado implementa la estrategia correcta de rebalanceo:
1. Detecta automáticamente la baja liquidez en USDT
2. Vende activos no estratégicos siguiendo prioridades definidas
3. Preserva activos de trading principal (ETHUSDT)
4. Respeta blacklist y circuit breakers
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime

from binance.client import Client
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
from app.core.config import settings
from app.core.circuit_breakers import CircuitBreakers
from app.core.strategy_blacklist import StrategyBlacklist
from app.db.session import SessionLocal
from app.models.trade import Trade
from app.services.trade_executor import get_trade_executor

logger = logging.getLogger(__name__)


class AutoRebalancerV2:
    """
    Servicio de rebalanceo automático V2 para mantener liquidez en USDT
    mediante la venta estratégica de activos no esenciales.
    """
    
    def __init__(self):
        # Configuración desde variables de entorno
        self.min_usdt_balance = float(os.getenv('MIN_USDT_BALANCE', '25.0'))
        self.target_usdt_balance = float(os.getenv('TARGET_USDT_BALANCE', '50.0'))
        self.enable_auto_rebalance = os.getenv('ENABLE_AUTO_REBALANCE', 'true').lower() == 'true'
        
        # Prioridades de activos para liquidación (de mayor a menor prioridad)
        self.asset_priority = os.getenv('REBALANCE_ASSET_PRIORITY', 'SPK,HOME,SIGN,BNB,BTC').split(',')
        
        # Activos protegidos (nunca se venden)
        self.protected_assets = ['ETHUSDT', 'ETH']  # Activos de trading principal
        
        # Usar cliente Binance Singleton
        from app.services.binance_client_singleton import get_binance_client_singleton
        self.binance_client = get_binance_client_singleton().client
        
        # Integración con sistemas de defensa
        self.circuit_breakers = CircuitBreakers()
        self.strategy_blacklist = StrategyBlacklist()
        
        # Estado del rebalanceo
        self.is_rebalancing = False
        self.last_rebalance = None
        
        logger.info(f"AutoRebalancer V2 inicializado - Min USDT: {self.min_usdt_balance}, Target: {self.target_usdt_balance}")
    
    async def check_and_rebalance(self) -> Dict:
        """
        Verifica liquidez y ejecuta rebalanceo automático si es necesario.
        
        Returns:
            Dict con el resultado del rebalanceo
        """
        if not self.enable_auto_rebalance:
            logger.info("Auto-rebalanceo desactivado")
            return {"status": "disabled", "message": "Auto-rebalance disabled"}
        
        if self.is_rebalancing:
            logger.warning("Rebalanceo ya en progreso, saltando ciclo")
            return {"status": "skipped", "reason": "already_rebalancing"}
        
        try:
            self.is_rebalancing = True
            logger.info("🔍 Iniciando verificación de liquidez")
            
            # Verificar circuit breakers
            if not await self._check_circuit_breakers():
                return {"status": "blocked", "reason": "circuit_breakers_active"}
            
            # Obtener balance actual de USDT
            current_usdt = await self._get_current_usdt_balance()
            logger.info(f"💰 Balance actual de USDT: {current_usdt:.2f}")
            
            # Verificar si necesita rebalanceo
            if current_usdt >= self.min_usdt_balance:
                logger.info(f"✅ Liquidez suficiente ({current_usdt:.2f} >= {self.min_usdt_balance})")
                return {"status": "sufficient", "current_usdt": current_usdt}
            
            # Calcular déficit y activar rebalanceo
            deficit = self.target_usdt_balance - current_usdt
            logger.warning(f"⚠️ Liquidez insuficiente. Déficit: {deficit:.2f} USDT")
            
            # Ejecutar rebalanceo
            result = await self._execute_liquidity_rebalance(deficit)
            
            self.last_rebalance = datetime.now()
            logger.info(f"🎯 Rebalanceo completado: {result}")
            
            return {
                "status": "success",
                "deficit_resolved": deficit,
                "result": result,
                "timestamp": self.last_rebalance.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error en rebalanceo automático: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            self.is_rebalancing = False
    
    async def _check_circuit_breakers(self) -> bool:
        """
        Verifica que los circuit breakers no estén activos.
        
        Returns:
            True si puede proceder, False si está bloqueado
        """
        try:
            # Verificar circuit breakers del sistema
            if self.circuit_breakers.is_trading_halted():
                logger.warning("🚨 Circuit breakers activos - rebalanceo bloqueado")
                return False
            
            # Verificar blacklist
            if self.strategy_blacklist.is_blacklist_active():
                logger.warning("🚨 Blacklist activa - rebalanceo bloqueado")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verificando circuit breakers: {e}")
            return False
    
    async def _get_current_usdt_balance(self) -> float:
        """
        Obtiene el balance actual de USDT.
        
        Returns:
            Balance de USDT
        """
        try:
            import asyncio
            
            # ✅ FIX: Obtener account info (non-blocking)
            account_info = await asyncio.to_thread(self.binance_client.get_account)
            
            for balance in account_info['balances']:
                if balance['asset'] == 'USDT':
                    free_balance = float(balance['free'])
                    locked_balance = float(balance['locked'])
                    return free_balance + locked_balance
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error obteniendo balance USDT: {e}")
            return 0.0
    
    async def _execute_liquidity_rebalance(self, target_deficit: float) -> Dict:
        """
        Ejecuta el rebalanceo para generar liquidez en USDT.
        
        Args:
            target_deficit: Cantidad de USDT que necesita generar
            
        Returns:
            Resultado del rebalanceo
        """
        try:
            # Obtener balance inicial de USDT
            initial_usdt_balance = await self._get_current_usdt_balance()
            logger.info(f"💰 Balance inicial de USDT: ${initial_usdt_balance:.2f}")
            logger.info(f"🔄 Iniciando rebalanceo de liquidez - Objetivo: {target_deficit:.2f} USDT")
            
            # Obtener balances actuales
            balances = await self._get_all_balances()
            logger.info(f"📊 Balances obtenidos: {len(balances)} activos con saldo")
            
            # Seleccionar activos para liquidación
            assets_to_sell = await self._select_assets_for_liquidation(balances, target_deficit)
            
            if not assets_to_sell:
                logger.warning("⚠️ No hay activos disponibles para liquidación")
                return {"status": "no_assets", "message": "No assets available for liquidation"}
            
            # Ejecutar ventas
            logger.info(f"💸 Ejecutando {len(assets_to_sell)} ventas...")
            results = await self._execute_sales(assets_to_sell)
            
            # Obtener balance final de USDT
            final_usdt_balance = await self._get_current_usdt_balance()
            usdt_generated = final_usdt_balance - initial_usdt_balance
            
            logger.info(f"💰 Balance final de USDT: ${final_usdt_balance:.2f}")
            logger.info(f"💵 USDT generado por liquidación: ${usdt_generated:.2f}")
            
            # Log del PnL realizado en las operaciones
            total_pnl = 0.0
            for result in results:
                if result.get('status') == 'success' and 'pnl' in result:
                    total_pnl += result['pnl']
                    logger.info(f"📈 PnL en {result['symbol']}: ${result['pnl']:.2f}")
            
            if total_pnl != 0:
                logger.info(f"📊 PnL total realizado: ${total_pnl:.2f}")
            
            logger.info(f"✅ Rebalanceo completado - USDT generado: ${usdt_generated:.2f}")
            
            return {
                "status": "success",
                "assets_sold": len(results),
                "usdt_generated": usdt_generated,
                "initial_usdt_balance": initial_usdt_balance,
                "final_usdt_balance": final_usdt_balance,
                "total_pnl": total_pnl,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error ejecutando rebalanceo de liquidez: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_all_balances(self) -> Dict[str, float]:
        """
        Obtiene balances de todos los activos.
        
        Returns:
            Dict con balances por activo
        """
        try:
            import asyncio
            
            # ✅ FIX: Obtener account info (non-blocking)
            account_info = await asyncio.to_thread(self.binance_client.get_account)
            balances = {}
            
            for balance in account_info['balances']:
                asset = balance['asset']
                free_balance = float(balance['free'])
                locked_balance = float(balance['locked'])
                total_balance = free_balance + locked_balance
                
                if total_balance > 0:
                    balances[asset] = total_balance
            
            logger.info(f"📊 Balances obtenidos: {len(balances)} activos con saldo")
            return balances
            
        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return {}
    
    async def _select_assets_for_liquidation(self, balances: Dict[str, float], target_deficit: float) -> List[Dict]:
        """
        Selecciona activos para liquidación siguiendo la estrategia de prioridades.
        
        Args:
            balances: Balances actuales
            target_deficit: Déficit a cubrir
            
        Returns:
            Lista de activos seleccionados para venta
        """
        selected_assets = []
        remaining_deficit = target_deficit
        
        logger.info(f"🎯 Seleccionando activos para liquidación - Déficit: {target_deficit:.2f} USDT")
        logger.info(f"📋 Lista de prioridades: {', '.join(self.asset_priority)}")
        logger.info(f"🛡️ Activos protegidos: {', '.join(self.protected_assets)}")
        
        # ✅ FIX: Paralelizar obtención de precios para logging
        logger.info("💰 Balances disponibles para liquidación:")
        price_tasks = []
        assets_to_log = []
        for asset in self.asset_priority:
            if asset in balances and balances[asset] > 0:
                symbol = f"{asset}USDT" if not asset.endswith('USDT') else asset
                assets_to_log.append((asset, symbol, balances[asset]))
                # Envolver en asyncio.to_thread para paralelizar
                price_tasks.append(
                    asyncio.to_thread(self.binance_client.get_symbol_ticker, symbol=symbol)
                )
        
        # Ejecutar todas las llamadas en paralelo
        if price_tasks:
            try:
                tickers = await asyncio.gather(*price_tasks, return_exceptions=True)
                for (asset, symbol, balance), ticker in zip(assets_to_log, tickers):
                    if isinstance(ticker, Exception):
                        logger.info(f"   {asset}: {balance:.6f} (precio no disponible)")
                    else:
                        try:
                            current_price = float(ticker['price'])
                            current_value_usdt = balance * current_price
                            logger.info(f"   {asset}: {balance:.6f} (~${current_value_usdt:.2f})")
                        except:
                            logger.info(f"   {asset}: {balance:.6f} (precio no disponible)")
            except Exception as e:
                logger.warning(f"Error obteniendo precios en paralelo: {e}")
                # Fallback: log sin precios
                for asset, _, balance in assets_to_log:
                    logger.info(f"   {asset}: {balance:.6f} (precio no disponible)")
        
        # ✅ FIX: Pre-obtener precios en paralelo para activos candidatos
        candidate_assets = []
        for asset in self.asset_priority:
            if remaining_deficit <= 0:
                break
            
            # Verificar filtros antes de obtener precio
            if self.strategy_blacklist.is_symbol_blacklisted(asset):
                continue
            if asset in self.protected_assets or f"{asset}USDT" in self.protected_assets:
                continue
            if asset not in balances or balances[asset] <= 0:
                continue
            
            symbol = f"{asset}USDT" if not asset.endswith('USDT') else asset
            candidate_assets.append((asset, symbol, balances[asset]))
        
        # Obtener precios en paralelo para todos los candidatos
        price_tasks = [
            asyncio.to_thread(self.binance_client.get_symbol_ticker, symbol=symbol)
            for _, symbol, _ in candidate_assets
        ]
        
        prices = {}
        if price_tasks:
            try:
                tickers = await asyncio.gather(*price_tasks, return_exceptions=True)
                for (asset, symbol, _), ticker in zip(candidate_assets, tickers):
                    if not isinstance(ticker, Exception):
                        try:
                            prices[asset] = float(ticker['price'])
                        except:
                            pass
            except Exception as e:
                logger.warning(f"Error obteniendo precios en paralelo: {e}")
        
        # Iterar por prioridades (de mayor a menor prioridad)
        for asset in self.asset_priority:
            if remaining_deficit <= 0:
                break
                
            logger.info(f"🔍 Evaluando {asset} (prioridad {self.asset_priority.index(asset) + 1})...")
                
            # Verificar si el activo está en la blacklist
            if self.strategy_blacklist.is_symbol_blacklisted(asset):
                logger.info(f"🚫 {asset} en blacklist - saltando")
                continue
            
            # Verificar si el activo está protegido
            if asset in self.protected_assets or f"{asset}USDT" in self.protected_assets:
                logger.info(f"🛡️ {asset} protegido - saltando")
                continue
            
            # Verificar si tenemos balance del activo
            if asset not in balances or balances[asset] <= 0:
                logger.info(f"💰 {asset} sin balance - saltando")
                continue
            
            # Calcular valor en USDT usando precio obtenido en paralelo
            try:
                symbol = f"{asset}USDT" if not asset.endswith('USDT') else asset
                
                # Usar precio obtenido en paralelo o obtener si no está disponible
                if asset in prices:
                    current_price = prices[asset]
                else:
                    # Fallback: obtener precio individualmente
                    ticker = await asyncio.to_thread(self.binance_client.get_symbol_ticker, symbol=symbol)
                    current_price = float(ticker['price'])
                
                current_value_usdt = balances[asset] * current_price
                
                logger.info(f"📊 {asset}: Balance={balances[asset]:.6f}, Precio=${current_price:.6f}, Valor=${current_value_usdt:.2f}")
                
                # Calcular cantidad a vender
                if current_value_usdt >= remaining_deficit:
                    # Vender solo lo necesario
                    quantity_to_sell = remaining_deficit / current_price
                    logger.info(f"🎯 {asset} - Vender solo lo necesario: {quantity_to_sell:.6f} (${remaining_deficit:.2f})")
                else:
                    # Vender todo el balance
                    quantity_to_sell = balances[asset]
                    logger.info(f"🎯 {asset} - Vender todo el balance: {quantity_to_sell:.6f} (${current_value_usdt:.2f})")
                
                # Verificar filtros de Binance
                if await self._validate_sale_parameters(symbol, quantity_to_sell):
                    selected_assets.append({
                        "asset": asset,
                        "symbol": symbol,
                        "quantity": quantity_to_sell,
                        "price": current_price,
                        "value_usdt": quantity_to_sell * current_price,
                        "priority": self.asset_priority.index(asset)
                    })
                    
                    remaining_deficit -= quantity_to_sell * current_price
                    logger.info(f"✅ {asset} seleccionado - Cantidad: {quantity_to_sell:.6f}, Valor: ${quantity_to_sell * current_price:.2f}, Déficit restante: ${remaining_deficit:.2f}")
                else:
                    logger.warning(f"❌ {asset} no cumple filtros de Binance")
                
            except Exception as e:
                logger.error(f"Error procesando {asset}: {e}")
                continue
        
        logger.info(f"📋 Selección completada - {len(selected_assets)} activos seleccionados")
        if selected_assets:
            total_value = sum(asset['value_usdt'] for asset in selected_assets)
            logger.info(f"💰 Valor total a liquidar: ${total_value:.2f} USDT")
        return selected_assets
    
    async def _validate_sale_parameters(self, symbol: str, quantity: float) -> bool:
        """
        Valida que los parámetros de venta cumplan con los filtros de Binance.
        
        Args:
            symbol: Símbolo a vender
            quantity: Cantidad a vender
            
        Returns:
            True si es válido, False si no
        """
        try:
            # Obtener información del símbolo
            symbol_info = self.binance_client.get_symbol_info(symbol=symbol)
            filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}
            
            # Verificar LOT_SIZE
            lot_size = filters.get("LOT_SIZE", {})
            if lot_size:
                min_qty = float(lot_size.get("minQty", 0))
                max_qty = float(lot_size.get("maxQty", float('inf')))
                step_size = float(lot_size.get("stepSize", 0))
                
                # Ajustar cantidad según step size ANTES de validar
                if step_size > 0:
                    # CORRECCIÓN: Evitar redondeo a 0 cuando step_size es muy grande
                    if quantity < step_size:
                        # Si la cantidad es menor que el step_size, usar el min_qty si es posible
                        if min_qty > 0 and min_qty <= max_qty:
                            quantity = min_qty
                        else:
                            logger.warning(f"❌ {symbol} - Cantidad {quantity} menor que step_size {step_size} y no hay min_qty válido")
                            return False
                    else:
                        quantity = round(quantity / step_size) * step_size
                
                # Verificar que la cantidad ajustada sea válida
                if quantity < min_qty:
                    logger.warning(f"❌ {symbol} - Cantidad ajustada {quantity} menor que mínimo {min_qty}")
                    return False
                if quantity > max_qty:
                    logger.warning(f"❌ {symbol} - Cantidad ajustada {quantity} mayor que máximo {max_qty}")
                    return False
            
            # Verificar MIN_NOTIONAL
            min_notional = float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 10))
            current_price = float(self.binance_client.get_symbol_ticker(symbol=symbol)['price'])
            notional_value = quantity * current_price
            
            if notional_value < min_notional:
                logger.warning(f"❌ {symbol} - Valor notional insuficiente: {notional_value:.2f} < {min_notional}")
                return False
            
            logger.info(f"✅ {symbol} - Parámetros válidos: cantidad={quantity:.6f}, valor=${notional_value:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error validando parámetros de {symbol}: {e}")
            return False
    
    async def _execute_sales(self, assets_to_sell: List[Dict]) -> List[Dict]:
        """
        Ejecuta las ventas de los activos seleccionados.
        
        Args:
            assets_to_sell: Lista de activos para vender
            
        Returns:
            Lista de resultados de ventas
        """
        results = []
        
        for asset_info in assets_to_sell:
            try:
                symbol = asset_info['symbol']
                quantity = asset_info['quantity']
                
                # Obtener información del símbolo para ajustar precisión
                symbol_info = self.binance_client.get_symbol_info(symbol=symbol)
                filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}
                
                # Ajustar cantidad según filtros de Binance
                lot_size = filters.get("LOT_SIZE", {})
                if lot_size:
                    step_size = float(lot_size.get("stepSize", 0.001))
                    min_qty = float(lot_size.get("minQty", 0.001))
                    
                    # Redondear cantidad según step size
                    if step_size > 0:
                        quantity = round(quantity / step_size) * step_size
                    
                    # Verificar cantidad mínima
                    if quantity < min_qty:
                        logger.warning(f"❌ {symbol} - Cantidad {quantity} menor que mínimo {min_qty}")
                        results.append({
                            "asset": asset_info['asset'],
                            "symbol": symbol,
                            "status": "error",
                            "error": f"Quantity {quantity} below minimum {min_qty}"
                        })
                        continue
                
                logger.info(f"💸 Vendiendo {symbol} - Cantidad: {quantity:.8f}")
                
                # Ejecutar orden de venta CON actualización automática de balances
                trade_executor = get_trade_executor()
                order = trade_executor.execute_market_sell(
                    symbol=symbol,
                    quantity=str(quantity)
                )
                
                # Guardar trade en base de datos (el balance ya fue actualizado por TradeExecutor)
                if order.get('status') == 'FILLED':
                    self._save_trade_to_db(
                        symbol=symbol,
                        side="SELL",
                        quantity=quantity,
                        price=asset_info['price'],
                        order_id=order.get('orderId')
                    )
                
                results.append({
                    "asset": asset_info['asset'],
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": asset_info['price'],
                    "value_usdt": asset_info['value_usdt'],
                    "order_id": order.get('orderId'),
                    "status": "success"
                })
                
                logger.info(f"✅ Venta exitosa: {symbol} - ${asset_info['value_usdt']:.2f}")
                
            except Exception as e:
                logger.error(f"❌ Error vendiendo {asset_info['asset']}: {e}")
                results.append({
                    "asset": asset_info['asset'],
                    "symbol": asset_info['symbol'],
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def _save_trade_to_db(self, symbol: str, side: str, quantity: float, price: float, order_id: str) -> None:
        """
        Guarda un trade en la base de datos.
        
        Args:
            symbol: Símbolo del trade
            side: Lado del trade (BUY/SELL)
            quantity: Cantidad
            price: Precio
            order_id: ID de la orden
        """
        try:
            db = SessionLocal()
            trade = Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=price,
                timestamp=datetime.utcnow()
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            logger.info(f"💾 Trade guardado en BD: {side} {quantity} {symbol} @ ${price:.6f}")
            db.close()
        except Exception as e:
            logger.error(f"Error guardando trade en BD: {e}")
            if db:
                db.close()
    
    async def get_rebalance_status(self) -> Dict:
        """
        Obtiene el estado actual del rebalanceo.
        
        Returns:
            Estado del rebalanceo
        """
        try:
            current_usdt = await self._get_current_usdt_balance()
            balances = await self._get_all_balances()
            
            # Calcular activos disponibles para liquidación
            available_assets = []
            for asset in self.asset_priority:
                if asset in balances and balances[asset] > 0:
                    if not self.strategy_blacklist.is_symbol_blacklisted(asset):
                        if asset not in self.protected_assets:
                            available_assets.append(asset)
            
            return {
                "is_rebalancing": self.is_rebalancing,
                "current_usdt_balance": current_usdt,
                "min_usdt_balance": self.min_usdt_balance,
                "target_usdt_balance": self.target_usdt_balance,
                "needs_rebalance": current_usdt < self.min_usdt_balance,
                "available_assets": available_assets,
                "protected_assets": self.protected_assets,
                "last_rebalance": self.last_rebalance.isoformat() if self.last_rebalance else None,
                "enabled": self.enable_auto_rebalance
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de rebalanceo: {e}")
            return {
                "error": str(e),
                "enabled": self.enable_auto_rebalance
            }


# Instancia global del AutoRebalancer V2
auto_rebalancer_v2 = AutoRebalancerV2()
