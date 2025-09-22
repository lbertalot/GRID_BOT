#!/usr/bin/env python3
"""
Script de Monitoreo Continuo para GridBot v2.5
Monitorea logs, métricas y estado del sistema cada 5 minutos
"""

import asyncio
import os
import sys
import time
import logging
import subprocess
import json
from datetime import datetime, timezone
from typing import Dict, List, Any
import httpx

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/continuous_monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ContinuousMonitor:
    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.prometheus_url = "http://localhost:9090"
        self.grafana_url = "http://localhost:3000"
        self.alert_thresholds = {
            "error_count": 5,  # Máximo 5 errores en 5 minutos
            "warning_count": 10,  # Máximo 10 warnings en 5 minutos
            "api_response_time": 2.0,  # Máximo 2 segundos de respuesta
            "memory_usage": 80,  # Máximo 80% de uso de memoria
            "cpu_usage": 90  # Máximo 90% de uso de CPU
        }
        self.last_check = datetime.now(timezone.utc)
        
    async def check_api_health(self) -> Dict[str, Any]:
        """Verificar salud de la API"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                start_time = time.time()
                response = await client.get(f"{self.api_base_url}/health")
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "response_time": response_time,
                        "status_code": response.status_code
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "response_time": response_time,
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "response_time": None
            }
    
    async def check_portfolio_status(self) -> Dict[str, Any]:
        """Verificar estado del portfolio"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_base_url}/api/portfolio/summary")
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "ok",
                        "cash_usdt": data.get("cash_usdt", 0),
                        "portfolio_total_usdt": data.get("portfolio_total_usdt", 0),
                        "assets_count": len(data.get("assets", []))
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
    
    async def check_prometheus_metrics(self) -> Dict[str, Any]:
        """Verificar métricas de Prometheus"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Verificar que Prometheus está funcionando
                response = await client.get(f"{self.prometheus_url}/api/v1/query?query=up")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        return {
                            "status": "ok",
                            "metrics_available": True
                        }
                    else:
                        return {
                            "status": "error",
                            "error": "Prometheus query failed"
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
    
    def check_docker_containers(self) -> Dict[str, Any]:
        """Verificar estado de contenedores Docker"""
        try:
            result = subprocess.run(
                ["docker-compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            container = json.loads(line)
                            containers.append({
                                "name": container.get("Name", ""),
                                "status": container.get("State", ""),
                                "health": container.get("Health", "")
                            })
                        except json.JSONDecodeError:
                            continue
                
                return {
                    "status": "ok",
                    "containers": containers,
                    "total_containers": len(containers)
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
    
    def check_recent_logs(self) -> Dict[str, Any]:
        """Verificar logs recientes para errores"""
        try:
            # Obtener logs de los últimos 5 minutos
            result = subprocess.run(
                ["docker-compose", "logs", "--since", "5m", "--tail", "100"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                logs = result.stdout
                error_count = logs.count("ERROR")
                warning_count = logs.count("WARNING")
                critical_count = logs.count("CRITICAL")
                
                return {
                    "status": "ok",
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "critical_count": critical_count,
                    "total_lines": len(logs.split('\n'))
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
    
    async def run_monitoring_cycle(self):
        """Ejecutar un ciclo completo de monitoreo"""
        logger.info("🔍 Iniciando ciclo de monitoreo continuo...")
        
        # Verificar salud de la API
        api_health = await self.check_api_health()
        logger.info(f"📡 API Health: {api_health['status']} (RT: {api_health.get('response_time', 'N/A')}s)")
        
        # Verificar estado del portfolio
        portfolio_status = await self.check_portfolio_status()
        if portfolio_status['status'] == 'ok':
            logger.info(f"💰 Portfolio: {portfolio_status['cash_usdt']} USDT (Total: {portfolio_status['portfolio_total_usdt']} USDT)")
        else:
            logger.error(f"❌ Portfolio Error: {portfolio_status.get('error', 'Unknown')}")
        
        # Verificar métricas de Prometheus
        prometheus_status = await self.check_prometheus_metrics()
        logger.info(f"📊 Prometheus: {prometheus_status['status']}")
        
        # Verificar contenedores Docker
        docker_status = self.check_docker_containers()
        logger.info(f"🐳 Docker: {docker_status['status']} ({docker_status.get('total_containers', 0)} containers)")
        
        # Verificar logs recientes
        logs_status = self.check_recent_logs()
        if logs_status['status'] == 'ok':
            logger.info(f"📝 Logs: {logs_status['error_count']} errors, {logs_status['warning_count']} warnings, {logs_status['critical_count']} critical")
            
            # Alertar si hay demasiados errores
            if logs_status['error_count'] > self.alert_thresholds['error_count']:
                logger.warning(f"⚠️ ALERTA: Demasiados errores ({logs_status['error_count']}) en los últimos 5 minutos")
            
            if logs_status['critical_count'] > 0:
                logger.error(f"🚨 CRÍTICO: {logs_status['critical_count']} errores críticos detectados")
        else:
            logger.error(f"❌ Logs Error: {logs_status.get('error', 'Unknown')}")
        
        # Verificar si hay actividad de trading no autorizada
        if logs_status['status'] == 'ok':
            trading_activity = self.check_trading_activity(logs_status.get('total_lines', 0))
            if trading_activity['unauthorized_trading']:
                logger.error(f"🚨 ALERTA CRÍTICA: Actividad de trading no autorizada detectada")
        
        logger.info("✅ Ciclo de monitoreo completado")
    
    def check_trading_activity(self, total_lines: int) -> Dict[str, Any]:
        """Verificar si hay actividad de trading no autorizada"""
        try:
            # Buscar indicadores de trading en los logs
            result = subprocess.run(
                ["docker-compose", "logs", "--since", "5m", "api", "celery_worker"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logs = result.stdout.lower()
                
                # Indicadores de trading
                trading_indicators = [
                    "order placed", "trade executed", "buy order", "sell order",
                    "order filled", "trade completed", "position opened"
                ]
                
                unauthorized_trading = any(indicator in logs for indicator in trading_indicators)
                
                return {
                    "status": "ok",
                    "unauthorized_trading": unauthorized_trading,
                    "indicators_found": [indicator for indicator in trading_indicators if indicator in logs]
                }
            else:
                return {
                    "status": "error",
                    "unauthorized_trading": False,
                    "error": result.stderr
                }
        except Exception as e:
            return {
                "status": "error",
                "unauthorized_trading": False,
                "error": str(e)
            }
    
    async def start_monitoring(self):
        """Iniciar monitoreo continuo"""
        logger.info("🚀 Iniciando monitoreo continuo de GridBot v2.5...")
        logger.info(f"⏰ Intervalo: 5 minutos")
        logger.info(f"📊 Umbrales: {self.alert_thresholds}")
        
        while True:
            try:
                await self.run_monitoring_cycle()
                logger.info("⏳ Esperando 5 minutos hasta el próximo ciclo...")
                await asyncio.sleep(300)  # 5 minutos
            except KeyboardInterrupt:
                logger.info("🛑 Monitoreo detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en ciclo de monitoreo: {e}")
                logger.info("⏳ Esperando 1 minuto antes de reintentar...")
                await asyncio.sleep(60)  # 1 minuto

async def main():
    monitor = ContinuousMonitor()
    await monitor.start_monitoring()

if __name__ == "__main__":
    asyncio.run(main())

