# 🚨 GridBot v2.5 - Guía de Solución Alertmanager

**Fecha**: 2026-01-03
**Problema**: Alertmanager no puede enviar notificaciones a Telegram
**Error**: `context deadline exceeded`

---

## 🔍 **DIAGNÓSTICO**

### Problema Identificado

**Síntoma**:
```
level=ERROR msg="Notify for alerts failed"
err="telegram.warning/webhook[0]: notify retry canceled after 1 attempts:
context deadline exceeded"
```

**Causa Raíz**:
1. ✅ Alertmanager está configurado para enviar a webhooks de la API
2. ❌ Los endpoints `/api/v1/alerts/telegram/*` **NO EXISTEN** en la API
3. ❌ Alertmanager espera respuesta y hace timeout (deadline exceeded)
4. ⚠️ Pero tú SÍ recibiste una alerta inicial en Telegram (funcionó parcialmente)

### Configuración Actual

**Alertmanager** (`docker/alertmanager/alertmanager.yml`):
```yaml
receivers:
  - name: 'telegram.critical'
    webhook_configs:
      - url: 'http://api:8000/api/v1/alerts/telegram/critical'
        send_resolved: true

  - name: 'telegram.warning'
    webhook_configs:
      - url: 'http://api:8000/api/v1/alerts/telegram/warning'
        send_resolved: true
```

**Problema**: Estos endpoints no existen en la API actual.

---

## ✅ **SOLUCIONES**

### Opción 1: Implementar Endpoints de Alertas (RECOMENDADO) ⭐

**Tiempo**: 15 minutos
**Impacto**: Sistema completo de alertas funcionando
**Prioridad**: ALTA

#### Paso 1: Crear el router de alertas

**Archivo**: `app/api/alerts.py` (NUEVO)

```python
"""
API endpoints para recibir alertas de Alertmanager y enviarlas a Telegram
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any
import logging
import os
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


async def send_telegram_message(message: str, severity: str = "info") -> bool:
    """Envía mensaje a Telegram con formato según severidad"""

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram no configurado (falta BOT_TOKEN o CHAT_ID)")
        return False

    # Emojis según severidad
    emoji_map = {
        "critical": "🚨",
        "warning": "⚠️",
        "info": "ℹ️",
        "resolved": "✅"
    }
    emoji = emoji_map.get(severity, "📢")

    formatted_message = f"{emoji} {message}"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": formatted_message,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(TELEGRAM_API_URL, json=payload)

            if response.status_code == 200:
                logger.info(f"✅ Alerta enviada a Telegram: {severity}")
                return True
            else:
                logger.error(f"❌ Error enviando a Telegram: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ Excepción enviando a Telegram: {e}")
        return False


def format_alert_message(alert: Dict[str, Any], severity: str) -> str:
    """Formatea la alerta en mensaje legible"""

    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status = alert.get("status", "firing")

    alertname = labels.get("alertname", "Unknown")
    instance = labels.get("instance", "unknown")
    summary = annotations.get("summary", "Sin descripción")
    description = annotations.get("description", "")

    # Emoji de estado
    status_emoji = "✅" if status == "resolved" else "🔥"

    # Construir mensaje
    lines = [
        f"<b>{status_emoji} ALERTA {severity.upper()}</b>",
        f"<b>Nombre:</b> {alertname}",
        f"<b>Instancia:</b> {instance}",
        f"<b>Estado:</b> {status}",
        "",
        f"<b>Resumen:</b> {summary}"
    ]

    if description:
        lines.append(f"<b>Detalle:</b> {description}")

    # Agregar timestamp
    starts_at = alert.get("startsAt", "")
    if starts_at:
        lines.append(f"<b>Inicio:</b> {starts_at}")

    return "\n".join(lines)


@router.post("/telegram/critical")
async def handle_critical_alert(request: Request):
    """
    Recibe alertas CRÍTICAS de Alertmanager y las envía a Telegram
    """
    try:
        payload = await request.json()
        alerts = payload.get("alerts", [])

        logger.info(f"📥 Recibidas {len(alerts)} alerta(s) CRÍTICA(S)")

        for alert in alerts:
            message = format_alert_message(alert, "critical")
            await send_telegram_message(message, severity="critical")

        return {"status": "ok", "alerts_processed": len(alerts)}

    except Exception as e:
        logger.error(f"❌ Error procesando alerta crítica: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telegram/warning")
async def handle_warning_alert(request: Request):
    """
    Recibe alertas WARNING de Alertmanager y las envía a Telegram
    """
    try:
        payload = await request.json()
        alerts = payload.get("alerts", [])

        logger.info(f"📥 Recibidas {len(alerts)} alerta(s) WARNING")

        for alert in alerts:
            message = format_alert_message(alert, "warning")
            await send_telegram_message(message, severity="warning")

        return {"status": "ok", "alerts_processed": len(alerts)}

    except Exception as e:
        logger.error(f"❌ Error procesando alerta warning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telegram/test")
async def test_telegram():
    """
    Endpoint de prueba para verificar que Telegram funciona
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {
            "status": "error",
            "message": "Telegram no configurado",
            "bot_token": bool(TELEGRAM_BOT_TOKEN),
            "chat_id": bool(TELEGRAM_CHAT_ID)
        }

    success = await send_telegram_message(
        "🧪 Test de alertas de GridBot v2.5\n\nSi ves este mensaje, Telegram funciona correctamente!",
        severity="info"
    )

    return {
        "status": "ok" if success else "error",
        "message": "Test enviado" if success else "Error enviando test",
        "bot_token": f"...{TELEGRAM_BOT_TOKEN[-10:]}" if TELEGRAM_BOT_TOKEN else None,
        "chat_id": TELEGRAM_CHAT_ID
    }
```

#### Paso 2: Registrar el router en main.py

**Archivo**: `app/main.py`

```python
# ... (imports existentes) ...
from app.api import alerts  # ✅ AGREGAR

# ... (código existente) ...

# Incluir routers
app.include_router(health.router)
app.include_router(trade.router)
app.include_router(prometheus_router.router)
app.include_router(alerts.router)  # ✅ AGREGAR
```

#### Paso 3: Reiniciar la API

```bash
cd /Users/leandrobertalot/Documents/grid_bot
docker-compose restart api
```

#### Paso 4: Probar el endpoint

```bash
# Test de Telegram
curl http://localhost:8000/api/v1/alerts/telegram/test

# Debería enviar un mensaje de prueba a tu Telegram
```

---

### Opción 2: Usar Script Python Directo (TEMPORAL)

**Tiempo**: 5 minutos
**Impacto**: Alertas funcionan pero fuera de la API
**Prioridad**: BAJA

Configurar Alertmanager para usar un script Python standalone:

**Archivo**: `docker/alertmanager/telegram_notifier.py` (NUEVO)

```python
#!/usr/bin/env python3
import sys
import json
import requests
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload, timeout=5)

if __name__ == "__main__":
    data = json.load(sys.stdin)
    alerts = data.get("alerts", [])

    for alert in alerts:
        alertname = alert.get("labels", {}).get("alertname", "Unknown")
        status = alert.get("status", "firing")
        summary = alert.get("annotations", {}).get("summary", "")

        message = f"🚨 <b>{alertname}</b>\nEstado: {status}\n{summary}"
        send_telegram(message)
```

**NO RECOMENDADO**: Requiere configurar volúmenes, permisos, etc.

---

### Opción 3: Silenciar Alertas Temporalmente (URGENTE)

**Tiempo**: 1 minuto
**Impacto**: Detiene el spam de errores en logs
**Prioridad**: URGENTE si los logs molestan

```bash
# Silenciar las alertas problemáticas en Alertmanager
curl -X POST http://localhost:9093/api/v1/silences -d '{
  "matchers": [
    {
      "name": "alertname",
      "value": "GridBotAPIDownWarning|DatabaseConnectionIssues",
      "isRegex": true
    }
  ],
  "startsAt": "2026-01-03T20:00:00Z",
  "endsAt": "2026-01-04T20:00:00Z",
  "createdBy": "admin",
  "comment": "Silenciando mientras se implementa fix de endpoints"
}'
```

---

## 🎯 **RECOMENDACIÓN**

### Plan de Acción Inmediato

**AHORA** (1 minuto):
```bash
# Silenciar alertas temporalmente
curl -X POST http://localhost:9093/api/v1/silences -H "Content-Type: application/json" -d '{
  "matchers": [{"name": "alertname", "value": ".*", "isRegex": true}],
  "startsAt": "2026-01-03T20:00:00Z",
  "endsAt": "2026-01-04T08:00:00Z",
  "createdBy": "admin",
  "comment": "Silenciando durante implementación de endpoints"
}'
```

**EN 15 MINUTOS** (cuando tengas tiempo):
1. Crear `app/api/alerts.py` con el código de la Opción 1
2. Agregar el router en `app/main.py`
3. Reiniciar API: `docker-compose restart api`
4. Probar: `curl http://localhost:8000/api/v1/alerts/telegram/test`
5. Remover silencio de Alertmanager

---

## 📊 **VERIFICACIÓN**

### Cómo saber si funcionó

```bash
# 1. Verificar que el endpoint existe
curl http://localhost:8000/api/v1/alerts/telegram/test

# 2. Deberías recibir un mensaje en Telegram

# 3. Verificar logs de Alertmanager (deben desaparecer los errores)
docker logs gridbot_alertmanager --tail 20

# 4. Simular una alerta
curl -X POST http://localhost:8000/api/v1/alerts/telegram/warning \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "labels": {"alertname": "TestAlert", "severity": "warning"},
      "annotations": {"summary": "Test manual de alerta"},
      "status": "firing"
    }]
  }'
```

---

## 🤔 **¿POR QUÉ RECIBISTE UNA ALERTA INICIAL?**

Probablemente:
1. La API estaba corriendo antes con esos endpoints (versión anterior)
2. O alguien implementó un endpoint temporal
3. O el mensaje vino de otra fuente

La configuración actual de Alertmanager **espera** esos endpoints, pero **no existen** en el código actual.

---

## 📝 **RESUMEN**

| Aspecto | Estado | Solución |
|---------|--------|----------|
| **Alertmanager** | ✅ Funciona | Ninguna |
| **Telegram Bot** | ✅ Configurado | Ninguna |
| **API Endpoints** | ❌ NO EXISTEN | Crear `alerts.py` |
| **Logs con errores** | ❌ Spam | Silenciar o implementar endpoints |

---

**Preparado por**: Cursor AI Agent
**Fecha**: 2026-01-03
**Siguiente Paso**: Implementar Opción 1 o silenciar con Opción 3

---
