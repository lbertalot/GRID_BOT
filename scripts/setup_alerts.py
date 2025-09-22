#!/usr/bin/env python3
"""
Script de Configuración de Alertas para GridBot v2.5
Configura alertas automáticas para errores críticos y monitoreo
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
        logging.FileHandler('logs/setup_alerts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlertConfiguration:
    def __init__(self):
        self.prometheus_url = "http://localhost:9090"
        self.grafana_url = "http://localhost:3000"
        self.alertmanager_url = "http://localhost:9093"
        self.alert_rules = {
            "high_error_rate": {
                "name": "GridBotHighErrorRate",
                "condition": "rate(gridbot_errors_total[5m]) > 0.1",
                "severity": "warning",
                "description": "Alta tasa de errores en GridBot"
            },
            "circuit_breaker_activated": {
                "name": "GridBotCircuitBreakerActivated",
                "condition": "gridbot_circuit_breakers_active_total > 0",
                "severity": "critical",
                "description": "Circuit breaker activado en GridBot"
            },
            "api_down": {
                "name": "GridBotAPIDown",
                "condition": "up{job=\"gridbot-api\"} == 0",
                "severity": "critical",
                "description": "API de GridBot no disponible"
            },
            "high_memory_usage": {
                "name": "GridBotHighMemoryUsage",
                "condition": "process_resident_memory_bytes / 1024 / 1024 / 1024 > 2",
                "severity": "warning",
                "description": "Alto uso de memoria en GridBot"
            },
            "trading_activity_detected": {
                "name": "GridBotTradingActivityDetected",
                "condition": "increase(gridbot_trades_executed_total[1m]) > 0",
                "severity": "info",
                "description": "Actividad de trading detectada"
            }
        }
    
    async def check_prometheus_availability(self) -> bool:
        """Verificar que Prometheus esté disponible"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.prometheus_url}/api/v1/query?query=up")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Error conectando a Prometheus: {e}")
            return False
    
    async def check_alertmanager_availability(self) -> bool:
        """Verificar que Alertmanager esté disponible"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.alertmanager_url}/api/v1/status")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Error conectando a Alertmanager: {e}")
            return False
    
    def create_prometheus_rules(self) -> str:
        """Crear reglas de Prometheus"""
        rules = {
            "groups": [
                {
                    "name": "gridbot_alerts",
                    "rules": []
                }
            ]
        }
        
        for rule_id, rule_config in self.alert_rules.items():
            rule = {
                "alert": rule_config["name"],
                "expr": rule_config["condition"],
                "for": "1m",
                "labels": {
                    "severity": rule_config["severity"],
                    "service": "gridbot"
                },
                "annotations": {
                    "summary": rule_config["description"],
                    "description": f"{{{{ $labels.instance }}}} - {rule_config['description']}"
                }
            }
            rules["groups"][0]["rules"].append(rule)
        
        return json.dumps(rules, indent=2)
    
    def create_alertmanager_config(self) -> str:
        """Crear configuración de Alertmanager"""
        config = {
            "global": {
                "smtp_smarthost": "localhost:587",
                "smtp_from": "gridbot@localhost"
            },
            "route": {
                "group_by": ["alertname"],
                "group_wait": "10s",
                "group_interval": "10s",
                "repeat_interval": "1h",
                "receiver": "web.hook"
            },
            "receivers": [
                {
                    "name": "web.hook",
                    "webhook_configs": [
                        {
                            "url": "http://localhost:5001/"
                        }
                    ]
                }
            ]
        }
        return json.dumps(config, indent=2)
    
    async def configure_prometheus_rules(self) -> bool:
        """Configurar reglas de Prometheus"""
        try:
            rules_content = self.create_prometheus_rules()
            
            # Guardar reglas en archivo
            with open("gridbot_alerts_rules.yml", "w") as f:
                f.write(rules_content)
            
            logger.info("✅ Reglas de Prometheus creadas: gridbot_alerts_rules.yml")
            return True
        except Exception as e:
            logger.error(f"❌ Error creando reglas de Prometheus: {e}")
            return False
    
    async def configure_alertmanager(self) -> bool:
        """Configurar Alertmanager"""
        try:
            config_content = self.create_alertmanager_config()
            
            # Guardar configuración en archivo
            with open("alertmanager_config.yml", "w") as f:
                f.write(config_content)
            
            logger.info("✅ Configuración de Alertmanager creada: alertmanager_config.yml")
            return True
        except Exception as e:
            logger.error(f"❌ Error creando configuración de Alertmanager: {e}")
            return False
    
    def create_telegram_alert_handler(self) -> str:
        """Crear handler de alertas para Telegram"""
        handler_code = '''#!/usr/bin/env python3
"""
Handler de Alertas para Telegram - GridBot v2.5
Recibe alertas de Prometheus y las envía a Telegram
"""

import json
import os
import sys
import logging
from flask import Flask, request
import requests

# Configuración
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_telegram_alert(alert_data):
    """Enviar alerta a Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Credenciales de Telegram no configuradas")
        return False
    
    try:
        # Formatear mensaje de alerta
        alert_name = alert_data.get("alerts", [{}])[0].get("labels", {}).get("alertname", "Unknown")
        severity = alert_data.get("alerts", [{}])[0].get("labels", {}).get("severity", "info")
        description = alert_data.get("alerts", [{}])[0].get("annotations", {}).get("description", "No description")
        
        emoji_map = {
            "critical": "🚨",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        
        emoji = emoji_map.get(severity, "ℹ️")
        
        message = f"{emoji} *GridBot Alert*\\n\\n"
        message += f"*Alert:* {alert_name}\\n"
        message += f"*Severity:* {severity}\\n"
        message += f"*Description:* {description}"
        
        # Enviar a Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        logger.info(f"✅ Alerta enviada a Telegram: {alert_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando alerta a Telegram: {e}")
        return False

@app.route("/", methods=["POST"])
def handle_alert():
    """Manejar alertas de Prometheus"""
    try:
        alert_data = request.get_json()
        logger.info(f"📨 Alerta recibida: {alert_data}")
        
        if send_telegram_alert(alert_data):
            return "OK", 200
        else:
            return "Error", 500
            
    except Exception as e:
        logger.error(f"❌ Error manejando alerta: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
'''
        
        with open("scripts/telegram_alert_handler.py", "w") as f:
            f.write(handler_code)
        
        os.chmod("scripts/telegram_alert_handler.py", 0o755)
        logger.info("✅ Handler de alertas de Telegram creado")
        return "scripts/telegram_alert_handler.py"
    
    def create_monitoring_script(self) -> str:
        """Crear script de monitoreo de alertas"""
        script_content = '''#!/bin/bash
# Script de monitoreo de alertas para GridBot v2.5

echo "🔍 Verificando estado de alertas..."

# Verificar Prometheus
if curl -s http://localhost:9090/api/v1/query?query=up > /dev/null 2>&1; then
    echo "✅ Prometheus funcionando"
else
    echo "❌ Prometheus no disponible"
    exit 1
fi

# Verificar Alertmanager
if curl -s http://localhost:9093/api/v1/status > /dev/null 2>&1; then
    echo "✅ Alertmanager funcionando"
else
    echo "❌ Alertmanager no disponible"
    exit 1
fi

# Verificar reglas de alerta
echo "📊 Verificando reglas de alerta..."
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="gridbot_alerts")'

echo "🎉 Sistema de alertas funcionando correctamente"
'''
        
        with open("scripts/check_alerts.sh", "w") as f:
            f.write(script_content)
        
        os.chmod("scripts/check_alerts.sh", 0o755)
        logger.info("✅ Script de verificación de alertas creado")
        return "scripts/check_alerts.sh"
    
    async def run_setup(self) -> Dict[str, Any]:
        """Ejecutar configuración completa de alertas"""
        logger.info("🚀 Iniciando configuración de alertas para GridBot v2.5...")
        
        results = {
            "prometheus_available": False,
            "alertmanager_available": False,
            "rules_created": False,
            "alertmanager_configured": False,
            "telegram_handler_created": False,
            "monitoring_script_created": False
        }
        
        # Verificar servicios
        logger.info("🔍 Verificando servicios...")
        results["prometheus_available"] = await self.check_prometheus_availability()
        results["alertmanager_available"] = await self.check_alertmanager_availability()
        
        if not results["prometheus_available"]:
            logger.error("❌ Prometheus no disponible")
            return results
        
        if not results["alertmanager_available"]:
            logger.warning("⚠️ Alertmanager no disponible")
        
        # Configurar reglas de Prometheus
        logger.info("📊 Configurando reglas de Prometheus...")
        results["rules_created"] = await self.configure_prometheus_rules()
        
        # Configurar Alertmanager
        logger.info("🔔 Configurando Alertmanager...")
        results["alertmanager_configured"] = await self.configure_alertmanager()
        
        # Crear handler de Telegram
        logger.info("📱 Creando handler de alertas de Telegram...")
        telegram_handler = self.create_telegram_alert_handler()
        results["telegram_handler_created"] = telegram_handler is not None
        
        # Crear script de monitoreo
        logger.info("🔧 Creando script de monitoreo...")
        monitoring_script = self.create_monitoring_script()
        results["monitoring_script_created"] = monitoring_script is not None
        
        # Mostrar resumen
        logger.info("\\n📋 Resumen de configuración:")
        for key, value in results.items():
            status = "✅" if value else "❌"
            logger.info(f"   {key}: {status}")
        
        return results

async def main():
    configurator = AlertConfiguration()
    results = await configurator.run_setup()
    
    print("\\n🎉 Configuración de alertas completada!")
    print("📊 Para verificar: ./scripts/check_alerts.sh")
    print("📱 Para iniciar handler de Telegram: python3 scripts/telegram_alert_handler.py")
    print("🔔 Para recargar Prometheus: curl -X POST http://localhost:9090/-/reload")

if __name__ == "__main__":
    asyncio.run(main())

