# Análisis de logs de producción (Papertrail/Heroku) y plan de acción

**Fecha:** 2026-02-17
**Fuente:** Logs de Heroku (grid-bot-ia), equivalentes a lo que recibe Papertrail.

---

## Resumen ejecutivo

En producción **no funcionan correctamente** la conexión con Binance (API y WebSocket) por restricción geográfica/IP de los servidores de Heroku. El resto del stack (API, worker Celery, Redis, Postgres, circuit breakers) está operativo; los breakers y el modo protegido se activan como defensa ante el fallo de Binance.

---

## 1. Lo que NO está funcionando correctamente

### 1.1 Binance – Ubicación restringida (crítico)

| Síntoma | Mensaje típico en logs |
|--------|-------------------------|
| API bloqueada | `Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms` |
| HTTP 451 | `Binance error de IP/ubicación (status 451) al crear listenKey` |
| WebSocket -2015 | `Error -2015 en conexión WS (IP no autorizada). Reintentando cada 300s` |

**Causa:** Los dynos de Heroku salen a internet desde IPs/región que Binance considera restringidas (política de elegibilidad). No es un fallo de credenciales ni de código.

**Impacto:**
- No hay trading real desde producción (API y User Data Stream bloqueados).
- Circuit breaker `system_integrity` se activa por `binance_net_fail`.
- Endpoints privados se deshabilitan (comportamiento esperado de defensa).

---

### 1.2 River / MLEngine en modo no operativo (secundario)

| Síntoma | Mensaje en logs |
|--------|------------------|
| ML deshabilitado | `River no disponible; MLEngine en modo no operativo` |

**Causa:** Depende de contexto (Binance/comisiones, etc.); al fallar Binance, el flujo que usa River queda en fallback.

**Impacto:** Bajo si no dependes del ML en producción; el fallback está implementado.

---

### 1.3 Unclosed client session / connector (asyncio) (menor)

| Síntoma | Mensaje en logs |
|--------|------------------|
| Al apagar web | `Unclosed client session` / `Unclosed connector` (aiohttp) |

**Causa:** Al hacer shutdown del proceso web no se cierran explícitamente las sesiones aiohttp (p. ej. en lifespan de FastAPI).

**Impacto:** Solo ruido en logs y posible pequeño retraso en cierre limpio; no afecta al trading.

---

## 2. Lo que SÍ está funcionando

- **API web:** Responde; `/health` y rutas públicas OK.
- **Worker Celery:** Conectado a Redis (rediss://), tareas registradas, `celery ready`.
- **Redis (Heroku):** Conectividad y uso normal; métricas en logs.
- **Circuit breakers:** Se activan correctamente ante fallo de Binance (modo protegido).
- **Papertrail:** Drain activo; logs de app, router y Redis llegando (plan Choklad, 10 MB/día).
- **Log level:** Con `LOG_LEVEL=WARNING` y `ACCESS_LOG=false` el volumen se mantiene dentro del plan gratuito.

*(Nota: Los errores antiguos de “Cannot connect to redis://localhost:6379” corresponden a un estado anterior ya corregido con REDIS_URL/CELERY_* del addon.)*

---

## 3. Plan de acción para mitigar los errores

### Prioridad 1 – Habilitar Binance en producción (trading real)

**Objetivo:** Que la app en producción pueda llamar a la API de Binance y, si aplica, al User Data Stream.

| Acción | Descripción | Esfuerzo |
|--------|-------------|----------|
| **A. Desplegar en región permitida** | Mover la app a un VPS o PaaS en una región/IP no restringida por Binance (consultar términos Binance y su lista de países/restricciones). | Alto (cambio de host) |
| **B. Proxy saliente (si Binance lo permite)** | Usar un proxy HTTP(s) o SOCKS con IP en región permitida para las llamadas a Binance (y, si aplica, WebSocket). Requiere que Binance permita acceso vía proxy según sus términos. | Medio (config proxy + pruebas) |
| **C. Mantener solo desarrollo/local con Binance** | Dejar producción en Heroku como “solo lectura/métricas” y hacer trading real desde un entorno (local/VPS) donde Binance no restrinja. | Bajo (documentar y aceptar limitación) |

**Recomendación:** Confirmar con los términos de Binance qué opciones (región, proxy) son aceptables; luego elegir A o B si se quiere trading real desde un único despliegue “producción”.

---

### Prioridad 2 – Reducir ruido y mejorar cierre limpio (opcional)

| Acción | Descripción | Dónde |
|--------|-------------|--------|
| Cerrar sesiones aiohttp en lifespan | En el `lifespan` de FastAPI, al apagar la app cerrar explícitamente los `ClientSession` de aiohttp (p. ej. cliente usado para Binance o user stream). | `app/main.py` / donde se creen las sesiones |
| Evitar reintentos agresivos de listenKey | Si Binance sigue bloqueado (451/-2015), considerar aumentar el intervalo de reintento o desactivar User Stream cuando el breaker esté activo, para reducir líneas de log. | `app/services/binance_user_stream.py` |

---

### Prioridad 3 – Observabilidad y documentación

| Acción | Descripción |
|--------|-------------|
| Alertas en Papertrail | Configurar alertas en Papertrail (plan Choklad) para “Circuit breaker activado” o “Binance 451” si quieres notificación inmediata. |
| Runbook | En `Docs/operations/` documentar: “Binance 451 / -2015 en producción” → causa (IP/región), opciones (VPS/proxy) y pasos para comprobar breaker y endpoints. |
| Dashboard | Revisar en Grafana/Prometheus que las métricas de breaker y de salud de Binance reflejen el estado real (modo protegido cuando corresponda). |

---

## 4. Checklist rápido post-análisis

- [ ] Decidir estrategia Binance en producción: VPS/proxy (A/B) o solo desarrollo/local (C).
- [ ] Si se usa proxy: implementar y probar en staging; verificar términos Binance.
- [ ] (Opcional) Cerrar sesiones aiohttp en lifespan para eliminar “Unclosed client session”.
- [ ] (Opcional) Ajustar reintentos/condiciones del User Stream cuando el breaker esté activo.
- [ ] Añadir runbook “Binance restringido en Heroku” en Docs/operations.
- [ ] Configurar alertas en Papertrail para errores críticos (breaker, 451) si se desea.

---

## 5. Referencia de mensajes clave en Papertrail

Para búsquedas útiles en Papertrail:

| Buscar | Interpretación |
|--------|-----------------|
| `binance_net_fail` / `system_integrity` | Circuit breaker activado por fallo de red/restricción Binance. |
| `451` / `restricted location` | Binance bloqueando por IP/ubicación. |
| `-2015` | WebSocket User Stream: IP no autorizada. |
| `River no disponible` | MLEngine en fallback; no crítico si no usas ML. |
| `Unclosed client session` | Limpieza al shutdown; prioridad baja. |
| `Cannot connect to redis://localhost` | Ya no debería aparecer; si aparece, revisar REDIS_URL en Heroku. |
