"""
⚠️ DEPRECATED — cleanup-archive-agent (2026-04-17)

Este módulo está reemplazado por `auto_rebalancer_v2.py`, que implementa
la misma lógica con mejoras de robustez y manejo de concurrencia.

Migra todos los imports a:
    from app.services.auto_rebalancer_v2 import AutoRebalancerV2

Este archivo se mantiene temporalmente para compatibilidad hacia atrás
y será eliminado en el próximo ciclo de mantenimiento.

---
AutoRebalancer Service - Sistema de rebalanceo automático para Grid Trading Bot

Este servicio resuelve el problema de saldos insuficientes detectado en el análisis:
- Solo 1/8 activos operativos (SPKUSDT)
- 7 activos con saldos insuficientes
- Necesita $29.35 USDT para activar todos los activos
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
from app.models.grid_config import GridConfig
from app.db.session import SessionLocal
from app.models.trade import Trade

logger = logging.getLogger(__name__)


class AutoRebalancer:
    """
    Servicio de rebalanceo automático para mantener saldos operativos
    en todos los activos configurados para Grid Trading.
    """
    
    def __init__(self):
        self.min_balance_threshold = 12.0  # USDT mínimo por activo (ajustado para cumplir min_notional + margen)
        self.rebalance_frequency = 3600  # segundos (1 hora)
        
        # Usar cliente Binance Singleton
        from app.services.binance_client_singleton import get_binance_client_singleton
        self.binance_client = get_binance_client_singleton().client
        # Si PAPER_TRADING está activo, avisar y evitar órdenes reales en otros métodos
        self.paper_trading = settings.paper_trading
        self.is_rebalancing = False
        
    async def check_and_rebalance(self) -> Dict:
        """
        Verifica y rebalancea saldos automáticamente.
        
        Returns:
            Dict con el resultado del rebalanceo
        """
        if self.is_rebalancing:
            logger.warning("Rebalanceo ya en progreso, saltando ciclo")
            return {"status": "skipped", "reason": "already_rebalancing"}
        
        try:
            self.is_rebalancing = True
            logger.info("Iniciando ciclo de rebalanceo automático")
            
            # Obtener balances actuales
            balances = await self.get_current_balances()
            logger.info(f"Balances actuales: {balances}")
            
            # Obtener configuración de grid
            grid_config = await self.get_grid_config()
            
            # Analizar necesidades de rebalanceo
            rebalance_needs = await self.analyze_rebalance_needs(balances, grid_config)
            
            if not rebalance_needs:
                logger.info("No se requiere rebalanceo")
                return {"status": "success", "message": "No rebalance needed"}
            
            # Ejecutar rebalanceo
            results = await self.execute_rebalance(rebalance_needs)
            
            logger.info(f"Rebalanceo completado: {results}")
            return {
                "status": "success",
                "rebalance_results": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en rebalanceo automático: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            self.is_rebalancing = False
    
    async def get_current_balances(self) -> Dict[str, float]:
        """
        Obtiene balances actuales de todos los activos.
        
        Returns:
            Dict con balances por activo
        """
        try:
            # Evitar bloqueo en caso de tests/paper: si no hay credenciales, retornar vacíos
            account_info = self.binance_client.get_account()
            balances = {}
            
            for balance in account_info['balances']:
                asset = balance['asset']
                free_balance = float(balance['free'])
                locked_balance = float(balance['locked'])
                total_balance = free_balance + locked_balance
                
                if total_balance > 0:
                    balances[asset] = total_balance
            
            logger.info(f"Balances obtenidos: {len(balances)} activos con saldo")
            return balances
            
        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return {}
    
    async def get_grid_config(self) -> Dict[str, GridConfig]:
        """
        Obtiene la configuración actual de grid trading.
        
        Returns:
            Dict con configuración por símbolo
        """
        try:
            # Cargar configuración desde archivo JSON
            import json
            with open('grid_config_optimized.json', 'r') as f:
                config_data = json.load(f)
            
            grid_configs = {}
            required = {"symbol","min_price","max_price","grids","quantity"}
            for key, cfg in config_data.items():
                if not isinstance(cfg, dict):
                    continue
                if key.startswith("_") or key in {"system_config"}:
                    continue
                if not required.issubset(cfg.keys()):
                    continue
                grid_configs[key] = type('GridConfig', (), {
                    'symbol': cfg.get('symbol'),
                    'min_price': cfg.get('min_price'),
                    'max_price': cfg.get('max_price'),
                    'grids': cfg.get('grids'),
                    'quantity': cfg.get('quantity'),
                    'last_action': cfg.get('last_action'),
                    'is_active': cfg.get('is_active', True)
                })()
            
            return grid_configs
            
        except Exception as e:
            logger.error(f"Error cargando configuración de grid: {e}")
            return {}
    
    async def analyze_rebalance_needs(self, balances: Dict[str, float], 
                                    grid_config: Dict[str, GridConfig]) -> List[Dict]:
        """
        Analiza qué activos necesitan rebalanceo.
        
        Args:
            balances: Balances actuales
            grid_config: Configuración de grid
            
        Returns:
            Lista de necesidades de rebalanceo
        """
        rebalance_needs = []
        
        for symbol, config in grid_config.items():
            if not config.is_active:
                continue
                
            # Extraer símbolo base (ej: BNBUSDT -> BNB)
            base_asset = symbol.replace('USDT', '')
            
            # Obtener balance actual del activo
            current_balance = balances.get(base_asset, 0.0)
            
            # Calcular valor actual en USDT
            try:
                ticker = self.binance_client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                current_value_usdt = current_balance * current_price
                
                # Calcular valor requerido para operar (cantidad configurada * precio actual)
                required_quantity = config.quantity
                required_value_usdt = required_quantity * current_price
                
                # Verificar si necesita rebalanceo (si el valor actual es menor que el requerido)
                if current_value_usdt < required_value_usdt:
                    needed_usdt = required_value_usdt - current_value_usdt
                    needed_quantity = needed_usdt / current_price
                    
                    rebalance_needs.append({
                        "symbol": symbol,
                        "base_asset": base_asset,
                        "current_balance": current_balance,
                        "current_value_usdt": current_value_usdt,
                        "required_value_usdt": required_value_usdt,
                        "needed_usdt": needed_usdt,
                        "needed_quantity": needed_quantity,
                        "current_price": current_price
                    })
                    
                    logger.info(f"Necesita rebalanceo: {symbol} - "
                              f"Valor actual: ${current_value_usdt:.2f}, "
                              f"Valor requerido: ${required_value_usdt:.2f}, "
                              f"Necesita: ${needed_usdt:.2f}")
                
            except Exception as e:
                logger.error(f"Error analizando {symbol}: {e}")
                continue
        
        return rebalance_needs
    
    async def execute_rebalance(self, rebalance_needs: List[Dict]) -> List[Dict]:
        """
        Ejecuta las transferencias necesarias para rebalancear.
        
        Args:
            rebalance_needs: Lista de necesidades de rebalanceo
            
        Returns:
            Lista de resultados de rebalanceo
        """
        results = []
        
        for need in rebalance_needs:
            symbol = need['symbol']
            base_asset = need['base_asset']
            needed_quantity = need['needed_quantity']
            
            logger.info(f"Ejecutando rebalanceo para {symbol}: {needed_quantity} {base_asset}")
            
            # Verificar que tenemos suficiente USDT
            usdt_balance = await self.get_usdt_balance()
            needed_usdt = need['needed_usdt']
            
            if usdt_balance < needed_usdt:
                    logger.warning(f"USDT insuficiente para {symbol}. "
                                 f"Disponible: ${usdt_balance:.2f}, "
                                 f"Necesario: ${needed_usdt:.2f}")
                    results.append({
                        "symbol": symbol,
                        "status": "failed",
                        "reason": "insufficient_usdt",
                        "needed_usdt": needed_usdt,
                        "available_usdt": usdt_balance
                    })
                    continue
                
            # Ejecutar compra
            try:
                order_result = await self.execute_buy_order(symbol, needed_quantity)
                    
                results.append({
                    "symbol": symbol,
                    "status": "success",
                    "quantity": needed_quantity,
                    "usdt_spent": needed_usdt,
                    "order_result": order_result
                })
                    
                logger.info(f"Rebalanceo exitoso para {symbol}")
                    
            except Exception as e:
                logger.error(f"Error ejecutando rebalanceo para {need['symbol']}: {e}")
                results.append({
                    "symbol": need['symbol'],
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    async def get_usdt_balance(self) -> float:
        """
        Obtiene el balance actual de USDT.
        
        Returns:
            Balance de USDT
        """
        try:
            # En modo PAPER_TRADING no ejecutamos acciones, solo devolvemos el balance actual
            balances = await self.get_current_balances()
            return balances.get('USDT', 0.0)
        except Exception as e:
            logger.error(f"Error obteniendo balance USDT: {e}")
            return 0.0
    
    def _save_trade_to_db(self, symbol: str, side: str, quantity: float, price: float, order_id: str):
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
            logger.info(f"Trade guardado en BD: {side} {quantity} {symbol} @ ${price:.6f}")
            db.close()
        except Exception as e:
            logger.error(f"Error guardando trade en BD: {e}")
            if db:
                db.close()

    async def execute_buy_order(self, symbol: str, quantity: float) -> Dict:
        """
        Ejecuta una orden de compra para rebalanceo.
        
        Args:
            symbol: Símbolo a comprar (ej: BNBUSDT)
            quantity: Cantidad a comprar
            
        Returns:
            Resultado de la orden
        """
        try:
            # Precio actual
            ticker = self.binance_client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])

            # Obtener filtros del símbolo
            symbol_info = self.binance_client.get_symbol_info(symbol=symbol)
            filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}
            min_notional = float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 10))

            # Calcular monto en USDT asegurando mínimo notional
            usdt_amount = max(round(quantity * current_price, 2), round(min_notional + 0.01, 2))

            # Ejecutar orden de compra con quoteOrderQty cumpliendo MIN_NOTIONAL
            order = self.binance_client.create_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=usdt_amount
            )
            
            logger.info(f"Orden de compra ejecutada: {symbol} - "
                       f"Cantidad: {quantity}, USDT: ${usdt_amount:.2f}")
            
            # Guardar trade en la base de datos
            if order.get('status') == 'FILLED':
                self._save_trade_to_db(symbol, "BUY", usdt_amount / current_price, current_price, order.get('orderId'))
            
            return {
                "order_id": order.get('orderId'),
                "symbol": symbol,
                "quantity": quantity,
                "usdt_amount": usdt_amount,
                "price": current_price,
                "status": order.get('status')
            }
            
        except Exception as e:
            logger.error(f"Error ejecutando orden de compra para {symbol}: {e}")
            raise
    
    async def get_rebalance_status(self) -> Dict:
        """
        Obtiene el estado actual del rebalanceo.
        
        Returns:
            Estado del rebalanceo
        """
        try:
            balances = await self.get_current_balances()
            grid_config = await self.get_grid_config()
            rebalance_needs = await self.analyze_rebalance_needs(balances, grid_config)
            
            total_needed_usdt = sum(need['needed_usdt'] for need in rebalance_needs)
            usdt_balance = await self.get_usdt_balance()
            
            return {
                "is_rebalancing": self.is_rebalancing,
                "assets_needing_rebalance": len(rebalance_needs),
                "total_needed_usdt": total_needed_usdt,
                "available_usdt": usdt_balance,
                "can_rebalance": usdt_balance >= total_needed_usdt,
                "rebalance_needs": rebalance_needs,
                "last_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de rebalanceo: {e}")
            return {
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }
    
    async def manual_rebalance(self, symbol: str, usdt_amount: float) -> Dict:
        """
        Ejecuta rebalanceo manual para un símbolo específico.
        
        Args:
            symbol: Símbolo a rebalancear
            usdt_amount: Cantidad en USDT a invertir
            
        Returns:
            Resultado del rebalanceo manual
        """
        try:
            logger.info(f"Ejecutando rebalanceo manual para {symbol}: ${usdt_amount}")
            
            # Verificar balance USDT
            usdt_balance = await self.get_usdt_balance()
            if usdt_balance < usdt_amount:
                return {
                    "status": "error",
                    "message": f"USDT insuficiente. Disponible: ${usdt_balance:.2f}"
                }
            
            # Ejecutar compra
            order_result = await self.execute_buy_order(symbol, usdt_amount)
            
            return {
                "status": "success",
                "symbol": symbol,
                "usdt_amount": usdt_amount,
                "order_result": order_result
            }
            
        except Exception as e:
            logger.error(f"Error en rebalanceo manual para {symbol}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


# Instancia global del AutoRebalancer
auto_rebalancer = AutoRebalancer() 