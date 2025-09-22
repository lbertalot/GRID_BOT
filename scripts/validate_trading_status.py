#!/usr/bin/env python3
"""
Script de Validación de Estado de Trading para GridBot v2.5
Verifica que el trading automático esté desactivado y el sistema esté seguro
"""

import asyncio
import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
import httpx

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/validate_trading_status.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingStatusValidator:
    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.critical_checks = {
            "trading_enabled": False,
            "paper_trading": True,
            "circuit_breakers_active": False,
            "no_active_orders": True,
            "no_recent_trades": True
        }
        
    async def check_trading_configuration(self) -> Dict[str, Any]:
        """Verificar configuración de trading"""
        try:
            # Verificar variables de entorno críticas
            env_vars = {
                "PAPER_TRADING": os.getenv("PAPER_TRADING", "true"),
                "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", "true"),
                "FORCE_REAL_MODE": os.getenv("FORCE_REAL_MODE", "false"),
                "TRADING_ENABLED": os.getenv("TRADING_ENABLED", "false")
            }
            
            return {
                "status": "ok",
                "paper_trading": env_vars["PAPER_TRADING"].lower() == "true",
                "testnet": env_vars["BINANCE_TESTNET"].lower() == "true",
                "force_real_mode": env_vars["FORCE_REAL_MODE"].lower() == "true",
                "trading_enabled": env_vars["TRADING_ENABLED"].lower() == "true"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def check_circuit_breakers(self) -> Dict[str, Any]:
        """Verificar estado de circuit breakers"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_base_url}/api/breakers/status")
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "ok",
                        "active_breakers": data.get("total_active", 0),
                        "critical_mode": data.get("critical_mode", False),
                        "breakers": data.get("breakers", {})
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def check_active_orders(self) -> Dict[str, Any]:
        """Verificar órdenes activas"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_base_url}/api/trades")
                if response.status_code == 200:
                    data = response.json()
                    active_orders = [trade for trade in data if trade.get("status") in ["PENDING", "SUBMITTED", "PARTIALLY_FILLED"]]
                    return {
                        "status": "ok",
                        "total_trades": len(data),
                        "active_orders": len(active_orders),
                        "orders": active_orders
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def check_recent_trading_activity(self) -> Dict[str, Any]:
        """Verificar actividad de trading reciente"""
        try:
            # Verificar logs de los últimos 10 minutos
            import subprocess
            result = subprocess.run([
                "docker-compose", "logs", "--since", "10m", "api", "celery_worker"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                logs = result.stdout.lower()
                
                # Indicadores de trading
                trading_indicators = [
                    "order placed", "trade executed", "buy order", "sell order",
                    "order filled", "trade completed", "position opened",
                    "order submitted", "trade successful"
                ]
                
                found_indicators = [indicator for indicator in trading_indicators if indicator in logs]
                
                return {
                    "status": "ok",
                    "trading_activity_detected": len(found_indicators) > 0,
                    "indicators_found": found_indicators,
                    "log_lines_checked": len(logs.split('\n'))
                }
            else:
                return {
                    "status": "error",
                    "error": result.stderr
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def check_portfolio_safety(self) -> Dict[str, Any]:
        """Verificar seguridad del portfolio"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_base_url}/api/portfolio/summary")
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "ok",
                        "cash_usdt": data.get("cash_usdt", 0),
                        "portfolio_total_usdt": data.get("portfolio_total_usdt", 0),
                        "assets_count": len(data.get("assets", [])),
                        "balance_stable": True  # Asumir estable si no hay cambios significativos
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def evaluate_safety_status(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluar estado de seguridad general"""
        safety_score = 0
        max_score = 5
        issues = []
        
        # Verificar configuración de trading
        if checks["trading_config"]["status"] == "ok":
            if checks["trading_config"]["paper_trading"]:
                safety_score += 1
            else:
                issues.append("⚠️ Paper trading desactivado")
            
            if not checks["trading_config"]["trading_enabled"]:
                safety_score += 1
            else:
                issues.append("⚠️ Trading habilitado")
            
            if checks["trading_config"]["testnet"]:
                safety_score += 1
            else:
                issues.append("⚠️ Testnet desactivado")
        else:
            issues.append("❌ Error verificando configuración de trading")
        
        # Verificar circuit breakers
        if checks["circuit_breakers"]["status"] == "ok":
            if checks["circuit_breakers"]["active_breakers"] == 0:
                safety_score += 1
            else:
                issues.append(f"⚠️ {checks['circuit_breakers']['active_breakers']} circuit breakers activos")
        else:
            issues.append("❌ Error verificando circuit breakers")
        
        # Verificar órdenes activas
        if checks["active_orders"]["status"] == "ok":
            if checks["active_orders"]["active_orders"] == 0:
                safety_score += 1
            else:
                issues.append(f"⚠️ {checks['active_orders']['active_orders']} órdenes activas")
        else:
            issues.append("❌ Error verificando órdenes activas")
        
        # Verificar actividad de trading
        if checks["trading_activity"]["status"] == "ok":
            if not checks["trading_activity"]["trading_activity_detected"]:
                safety_score += 1
            else:
                issues.append("⚠️ Actividad de trading detectada en logs")
        else:
            issues.append("❌ Error verificando actividad de trading")
        
        # Determinar estado general
        if safety_score == max_score:
            overall_status = "SAFE"
            status_emoji = "✅"
        elif safety_score >= max_score * 0.8:
            overall_status = "MOSTLY_SAFE"
            status_emoji = "⚠️"
        else:
            overall_status = "UNSAFE"
            status_emoji = "❌"
        
        return {
            "overall_status": overall_status,
            "status_emoji": status_emoji,
            "safety_score": safety_score,
            "max_score": max_score,
            "safety_percentage": (safety_score / max_score) * 100,
            "issues": issues
        }
    
    async def run_validation(self) -> Dict[str, Any]:
        """Ejecutar validación completa"""
        logger.info("🔍 Iniciando validación de estado de trading...")
        
        # Ejecutar todas las verificaciones
        checks = {
            "trading_config": await self.check_trading_configuration(),
            "circuit_breakers": await self.check_circuit_breakers(),
            "active_orders": await self.check_active_orders(),
            "trading_activity": await self.check_recent_trading_activity(),
            "portfolio_safety": await self.check_portfolio_safety()
        }
        
        # Evaluar estado de seguridad
        safety_evaluation = self.evaluate_safety_status(checks)
        
        # Mostrar resultados
        logger.info(f"📊 Estado de seguridad: {safety_evaluation['status_emoji']} {safety_evaluation['overall_status']}")
        logger.info(f"🎯 Puntuación: {safety_evaluation['safety_score']}/{safety_evaluation['max_score']} ({safety_evaluation['safety_percentage']:.1f}%)")
        
        if safety_evaluation['issues']:
            logger.warning("⚠️ Problemas detectados:")
            for issue in safety_evaluation['issues']:
                logger.warning(f"   {issue}")
        else:
            logger.info("✅ No se detectaron problemas de seguridad")
        
        # Mostrar detalles de cada verificación
        logger.info("\n📋 Detalles de verificación:")
        logger.info(f"   Trading Config: {checks['trading_config']['status']}")
        logger.info(f"   Circuit Breakers: {checks['circuit_breakers']['status']}")
        logger.info(f"   Active Orders: {checks['active_orders']['status']}")
        logger.info(f"   Trading Activity: {checks['trading_activity']['status']}")
        logger.info(f"   Portfolio Safety: {checks['portfolio_safety']['status']}")
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "safety_evaluation": safety_evaluation
        }
    
    async def start_continuous_validation(self, interval_minutes: int = 5):
        """Iniciar validación continua"""
        logger.info(f"🚀 Iniciando validación continua de estado de trading...")
        logger.info(f"⏰ Intervalo: {interval_minutes} minutos")
        
        while True:
            try:
                await self.run_validation()
                logger.info(f"⏳ Esperando {interval_minutes} minutos hasta la próxima validación...")
                await asyncio.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                logger.info("🛑 Validación continua detenida por el usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en validación: {e}")
                logger.info("⏳ Esperando 1 minuto antes de reintentar...")
                await asyncio.sleep(60)

async def main():
    validator = TradingStatusValidator()
    
    # Ejecutar validación única
    result = await validator.run_validation()
    
    # Guardar resultado
    with open('logs/trading_validation_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n🎉 Validación completada!")
    print(f"📊 Estado: {result['safety_evaluation']['status_emoji']} {result['safety_evaluation']['overall_status']}")
    print(f"🎯 Puntuación: {result['safety_evaluation']['safety_score']}/{result['safety_evaluation']['max_score']}")
    print(f"📋 Resultado guardado en: logs/trading_validation_result.json")

if __name__ == "__main__":
    asyncio.run(main())

