# GridBot v2.5 — Auditoría de Calidad y Preparación para Producción

## Resumen Ejecutivo
GridBot v2.5 muestra una arquitectura sólida con defensas (breakers, validación previa, métricas) y una suite de pruebas amplia. Sin embargo, detecté hallazgos críticos que deben corregirse antes de operar con dinero real: secretos versionados en el repo, endpoints sin autenticación que ejecutan lógica sensible con credenciales de Binance, generación de IDs no determinista que afecta idempotencia de órdenes, uso extensivo de `float` en cálculos monetarios, y falta de timeouts/backoff en I/O externo. Veredicto: Listo con Correcciones Críticas.

## Tabla de Hallazgos
| Archivo | Línea (Aprox.) | Pilar de Evaluación | Severidad | Descripción del Hallazgo | Recomendación / Código Sugerido |
| :--- | :---: | :--- | :---: | :--- | :--- |
| 19092025.env | 7-13, 57-58 | Seguridad | Crítica | Secretos reales versionados (API_KEY, TELEGRAM_BOT_TOKEN) | Eliminar archivo del repo, purgar del historial, rotar llaves. Usar `.env` en secretos locales/CI y plantillas sin valores reales. |
| app/api/prometheus.py | 74-155 | Seguridad | Alta | Endpoint `POST /update-pnl` sin autenticación que usa credenciales reales de Binance | Eliminar/privatizar el endpoint o añadir auth estricta y throttling. Preferir métrica pasiva expuesta en `/metrics` sin tocar proveedores. |
| app/api/metrics.py | 115-215 y 311-320 | Consistencia/Seguridad | Alta | Doble definición de `POST /metrics/update-pnl` (una sin auth, otra con auth) | Dejar una única ruta autenticada, o mover a tarea asíncrona interna. Evitar llamadas directas a Binance desde HTTP si no es imprescindible. |
| app/api/trade.py | 127-159 | Seguridad | Media-Alta | `GET /trades` sin autenticación expone histórico de operaciones | Proteger con `require_auth`. |
| app/api/trade.py | 394-401 | Seguridad | Media | `GET /grid_config` sin autenticación (posible filtración de configuración) | Proteger con `require_auth`. |
| app/core/middleware/prometheus_http.py | 29-33 | Observabilidad | Media | Alta cardinalidad: etiqueta `path` usa `request.url.path` sin normalizar | Usar la plantilla de ruta para bajar cardinalidad: 
```python
route = getattr(request.scope.get("route"), "path", request.url.path)
path = route
```
Además, limitar rutas dinámicas a patrones.
|
| app/core/middleware/prometheus_http.py | 9-20, 29-33 | Consistencia | Media | No incrementa métricas `gridbot_api_requests_total` y `api_request_duration_seconds` como definen las reglas | Llamar a utilidades centrales:
```python
from app.core.metrics import record_api_request
...
record_api_request(method, path, response.status_code, duration)
```
|
| app/services/binance_service.py | 231-257 | Robustez | Alta | Cálculo notional y comisiones con `float`; riesgo de precisión en dinero | Migrar a `Decimal` y cuantizar a `tickSize/stepSize`:
```python
from decimal import Decimal, ROUND_DOWN, getcontext
getcontext().prec = 28
price = Decimal(str(current_price))
qty = Decimal(str(quantity_info['adjusted_quantity']))
notional = (qty * price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
```
|
| app/services/order_validation.py | 121-173 | Robustez | Alta | Validación y redondeos monetarios con `float` y `%` (posibles fallos LOT_SIZE/MIN_NOTIONAL) | Usar `Decimal` y `quantize` para precio/cantidad; reemplazar `%` por operaciones Decimal y redondeos deterministas. |
| app/api/trade.py | 161-279 | Rendimiento/Robustez | Alta | Ruta `place_order` es `async` pero usa cliente síncrono de Binance (bloqueo del event loop) | Ejecutar I/O bloqueante en `run_in_executor` o usar cliente asíncrono/worker Celery para enviar órdenes. |
| app/exchanges/binance_client.py | 170-193 | Robustez | Alta | Llamadas `aiohttp` sin `timeout` ni backoff; reintentos caseros en otros lados | Añadir timeouts y tenacity:
```python
import tenacity
from aiohttp import ClientTimeout
@tenacity.retry(wait=tenacity.wait_exponential(max=10), stop=tenacity.stop_after_attempt(5))
async def _get(url):
  timeout = ClientTimeout(total=10)
  async with aiohttp.ClientSession(timeout=timeout) as s:
    async with s.get(url) as r: r.raise_for_status(); return await r.json()
```
|
| app/services/binance_service.py | 117-151, 283-300, 356-359 | Robustez | Alta | Sin timeouts/backoff al usar `python-binance` (puede colgar) | Envolver llamadas con `tenacity` y `recvWindow` prudente; abortar tras N reintentos y activar breaker `system_integrity`. |
| app/services/binance_client_singleton.py | 81-96 | Seguridad | Alta | `testnet` forzado a `False`, ignorando `BINANCE_TESTNET` | Respetar bandera de entorno para evitar operar en mainnet por error:
```python
testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
self._client = Client(api_key, api_secret, testnet=testnet)
```
|
| app/core/operation_tracker.py | 428-433 | Idempotencia | Crítica | `client_order_id` usa `hash()` de Python (no determinista entre procesos) | Usar hash estable (SHA-256 truncado):
```python
import hashlib
base = f"{asset}|{side}|{quantity}|{price}|{metadata}".encode()
suffix = hashlib.sha256(base).hexdigest()[:24]
return f"GRIDBOT_{suffix}"
```
|
| app/api/trade.py | 167-177 | Robustez | Media | Verificación de breakers con instancia nueva (`CircuitBreakers()`); no comparte estado global | Usar `request.app.state.breakers` o inyectar singleton compartido. Middleware ya protege, pero unificar fuente reduce errores. |
| app/core/integrity_monitor.py | 265-273 | Observabilidad/Robustez | Media | `check_database_health()` retorna 100 aun con error (enmascara fallos) | Retornar score bajo si falla, y registrar métrica/alerta; evitar falsos verdes. |
| app/db/session.py | 17-23 | Rendimiento | Media | Engine SQLAlchemy sin `pool_recycle`, `pool_size`, `pool_timeout` | Ajustar pool para producción:
```python
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=1800, pool_size=10, max_overflow=20, pool_timeout=30)
```
|
| app/core/config.py | 16-19 | Seguridad/Config | Media | `secret_key` por defecto débil, `debug=True` por defecto | Forzar valores seguros en producción y leer de entorno; validar que `DEBUG`=false y `SECRET_KEY` presente. |
| app/core/metrics.py | 351-370 | Observabilidad | Baja | Uso de API privada de métricas (`._value.get()`), y `print` | Usar getters públicos o mantener sólo exposición Prometheus; reemplazar `print` por logger estructurado. |
| app/main.py | 208-221 | Consistencia | Baja | Duplicación de routers/alias puede introducir rutas repetidas | Consolidar rutas y mantener un mapa claro; evitar múltiple `include_router` del mismo router salvo necesidad probada. |
| app/api/trade.py | 503-543 | Rendimiento/Monetario | Media | `reconciliation_summary` usa `float` y mezcla lógica de consulta/precio en ruta | Mover a servicio asíncrono con `Decimal`; proteger con auth si expone datos sensibles. |
| app/exchanges/binance_client.py | 365-375 | Seguridad | Media | `create_order`: comentario `TODO` firma HMAC; devolución mock | Documentar que no se usa en producción o implementar firma si se integra. |
| requirements.txt | varias | Seguridad/Optimización | Media | Paquetes pesados (tensorflow, vectorbt) instalados en prod; sin auditoría de CVEs | Mover a extras opcionales (dev/analysis). Ejecutar `pip-audit` en CI y fijar versiones seguras. |

## Resumen de Cobertura de Pruebas
- Cobertura funcional: amplia en áreas clave (circuit breakers, validación de órdenes, ciclo de trading, estrategias, caché Redis, endpoints básicos). Tests de integración via HTTP (`tests/test_api_endpoints.py`, `tests/test_trading_cycle.py`) verifican contractos y estados básicos.
- Brechas relevantes que requieren tests adicionales (prioridad alta):
  - Idempotencia de órdenes: `OperationTracker.generate_client_order_id` con hash estable y persistencia de estados; prueba de reintento sin duplicados.
  - Seguridad de endpoints: asegurar autenticación en `GET /trades`, `GET /grid_config`, eliminación de `POST /metrics/update-pnl` sin auth.
  - Tolerancia a fallos y reintentos: timeouts/backoff en `binance_service` y `exchanges/binance_client` con escenarios de red (timeouts, 5xx, -2015).
  - Normalización LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL con `Decimal` (bordes: stepSize muy pequeño, notional exacto al mínimo, rounding hacia abajo/arriba).
  - Middleware Prometheus: normalización de rutas y baja cardinalidad; asegurar incremento de `gridbot_api_requests_total` y `api_request_duration_seconds`.
- Brechas de cobertura (prioridad media):
  - `IntegrityGuardMiddleware` y `IntegrityMonitor` (modos crítico, umbrales de recuperación, salud DB/Redis).
  - `MetricsManager` consultas agregadas y métricas derivadas.
  - `paper_trading` estado persistente y cálculos PnL.
  - Configuración y pool de DB (fallos de conexión, reciclaje de conexiones).

## Recomendaciones Prioritarias (Plan de Acción)
1) Seguridad (bloqueadores para producción)
- Retirar secretos versionados y rotarlos. Proteger o eliminar endpoints sensibles sin auth (`/metrics/update-pnl`, `/grid_config`, `/trades`).
- Respetar `BINANCE_TESTNET` en singleton y añadir verificación de `TRADING_ENABLED`/`EMERGENCY_STOP` al inicio de tareas críticas.

2) Idempotencia y precisión monetaria
- Migrar cálculo monetario a `Decimal` en validación/ejecución. Cambiar generación de `client_order_id` a hash estable (SHA-256 truncado).

3) Tolerancia a fallos y rendimiento
- Añadir timeouts/backoff (tenacity) en llamadas a Binance (sync/async) y normalizar uso asíncrono (no bloquear event loop). Añadir pool tuning en SQLAlchemy.

4) Observabilidad
- Normalizar etiquetas de Prometheus (path templado) y unificar métricas `gridbot_*` en middleware. Añadir métricas de reintentos/fallos en I/O crítico.

5) Pruebas
- Agregar tests de seguridad, idempotencia, fallos de red y validación con `Decimal` para alcanzar ≥85% en módulos críticos.

---

Si necesitas, puedo abrir un PR aplicando los cambios mínimos y añadiendo los tests críticos propuestos.
