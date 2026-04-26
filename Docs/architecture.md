# GridBot v2.5 - Arquitectura del Sistema

> **Última actualización**: 2026-01-02
> **Auditor**: Senior Software Architect
> **Versión del sistema**: 2.5.0

## 📐 Visión General de la Arquitectura

GridBot v2.5 es un sistema de trading algorítmico implementado con **FastAPI** (API REST), **Celery** (procesamiento de tareas), **PostgreSQL** (persistencia), **Redis** (caché/broker), y **Prometheus/Grafana** (observabilidad), desplegado en contenedores **Docker**.

### Principios Arquitectónicos

1. **Separación de Responsabilidades**: `app/api` (endpoints), `app/services` (lógica de negocio), `app/core` (infraestructura)
2. **Event-Driven con Celery**: Tareas asíncronas orquestadas por Celery Beat
3. **Observabilidad Total**: Métricas Prometheus, logs estructurados, dashboards Grafana
4. **Defensa en Profundidad**: Validaciones multi-capa, circuit breakers, límites de riesgo
5. **Integridad Financiera**: Reconciliación continua con Binance, tracking de operaciones

---

## 🏗️ Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                      NGINX (Proxy Inverso)                       │
│                       Puerto 80 → API:8000                       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                     ┌────────────┴────────────┐
                     │   FastAPI Application   │
                     │  (app/main.py - 3 workers)
                     │                         │
                     │  Middlewares:           │
                     │  - CORS                 │
                     │  - PrometheusHTTP       │
                     │  - IntegrityGuard       │
                     │  - TrustedHost          │
                     └────────────┬────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
 ┌──────▼───────┐      ┌─────────▼──────────┐   ┌────────▼─────────┐
 │   API Layer  │      │   Services Layer   │   │   Core Layer     │
 │  (Routers)   │      │  (Business Logic)  │   │ (Infrastructure) │
 │              │      │                    │   │                  │
 │ - trade.py   │◄─────┤ - trading_tasks.py │◄──┤ - config.py      │
 │ - metrics.py │      │ - grid_strategy.py │   │ - circuit_breakers│
 │ - strategies │      │ - reconciliation   │   │ - balance_validator│
 │ - integrity  │      │ - binance_client   │   │ - operation_tracker│
 └──────┬───────┘      └─────────┬──────────┘   └────────┬─────────┘
        │                        │                       │
        │        ┌───────────────┴──────────┐           │
        │        │                          │           │
    ┌───▼────────▼──┐              ┌────────▼───────────▼────┐
    │  PostgreSQL   │              │   Redis                  │
    │  (gridbot DB) │              │  (Cache + Broker)        │
    │               │              │                          │
    │ - trades      │              │ - Balances Cache         │
    │ - grid_config │              │ - Cycle State            │
    │ - alerts      │              │ - Celery Tasks Queue     │
    └───────────────┘              └──────────┬───────────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │   Celery Workers    │
                                   │                     │
                                   │ - trading_cycle_tick │
                                   │ - assess_risk        │
                                   │ - dust_sweep         │
                                   │ - analyze_performance│
                                   └──────────┬──────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │   Celery Beat       │
                                   │  (Scheduler)        │
                                   │                     │
                                   │ Cron Jobs:          │
                                   │ - 60s: cycle_tick   │
                                   │ - 5m: risk_assess   │
                                   │ - 1d: performance   │
                                   └─────────────────────┘
```

---

## 🔄 Flujo de Datos: Ciclo de Trading

### 1. Inicio del Ciclo (cada 60s - Celery Beat)

```python
# app/services/trading_tasks.py:101
@celery_app.task
def trading_cycle_tick():
    """
    Tick cada 60s que orquesta un ciclo de 5 minutos:
    - 0-240s: Fase de Evaluación (recolección de datos, ML, decisión)
    - 240-300s: Fase de Ejecución (envío de órdenes)
    """
```

**Problemas Identificados**:
- ⚠️ **Race Condition Potencial**: Si un ciclo anterior no ha terminado en 60s, se puede solapar con el siguiente
- 🔴 **Falta de Lock Distribuido**: No hay mecanismo de lock en Redis para prevenir ejecuciones concurrentes
- ⚠️ **Sin timeout explícito**: Tareas Celery sin `soft_time_limit` o `time_limit`

### 2. Recolección de Datos de Mercado

```python
# app/services/market_data_collector.py
mdc = MarketDataCollector(ttl_seconds=5)
symbols = ["ETHUSDT"]  # ⚠️ Universo hardcodeado temporal
```

**Flujo**:
1. Obtiene precio actual de Binance REST API
2. Obtiene KLines (velas) para análisis técnico
3. **Cache**: TTL de 5 segundos en memoria (no Redis)

**Problemas**:
- 🔴 **Lazy Initialization Bloqueante** (LÍNEA CRÍTICA: `market_data_collector.py:~40`):
  ```python
  def __init__(self, ...):
      self._client = None  # Lazy initialization

  async def _get_sync_client(self):
      if self._client is None:
          self._client = Client(api_key, api_secret, testnet=False)
          # ⚠️ Constructor de Client es SINCRÓNICO y hace I/O bloqueante
  ```
- ⚠️ **Sin retry exponencial** en llamadas a Binance
- ⚠️ **No respeta recvWindow** en peticiones firmadas (por defecto 5000ms, puede fallar en servidores con alta latencia)

### 3. Evaluación de Estrategia (ML + Selector)

```python
# app/services/strategy_selector.py
selector = StrategySelector()
decision = selector.select_strategy(symbol, market_data, account_state)
```

**Decisión incluye**:
- `strategy_name`: "GridTrading", "Scalping", "RSI_MACD"
- `confidence`: 0.0 - 1.0
- `reasoning`: Explicación textual

**Filtros de Decisión**:
```python
MIN_DECISION_CONFIDENCE = 0.50  # Umbral de confianza
SAFE_MIN_USDT = 15.0            # Balance mínimo
```

### 4. Sizing y Validación de Orden

```python
# app/core/risk_manager.py
risk_manager = RiskManager()
position_size = risk_manager.calculate_position_size(...)

# app/services/order_validation.py
validator = OrderValidator(client)
is_valid = validator.validate_order(symbol, side, quantity, price)
```

**Validaciones Multi-Capa**:
1. **Exchange Info**: `PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL` (Binance)
2. **Balance**: Verifica USDT disponible
3. **Circuit Breakers**: Consulta estado de breakers
4. **Comisiones**: Calcula fee (0.1% por defecto)

**Problemas Críticos**:
- 🔴 **Race Condition en Balance** (LÍNEA: `trading_tasks.py:~180`):
  ```python
  balances = await manager.get_asset_balances()
  # ⚠️ Entre aquí y la orden, otro proceso puede consumir el balance
  # Sin lock optimista ni versionado
  ```
- 🔴 **Validación no atómica**: Entre validación y ejecución pueden cambiar condiciones de mercado

### 5. Ejecución de Orden y Tracking

```python
# app/services/binance_client_singleton.py
client_singleton = get_binance_client_singleton()
order = client_singleton.client.create_order(
    symbol=symbol,
    side=side,
    type='MARKET',
    quantity=quantity,
    newClientOrderId=client_order_id  # ✅ Idempotencia
)
```

**Flujo Post-Orden**:
1. **Registro en BD**: Inserta en tabla `trades`
2. **Operation Tracker**: Registra operación en memoria
3. **Métricas Prometheus**: Incrementa counters

**Problemas**:
- ⚠️ **Sin WebSocket para fills en tiempo real**: Depende de polling REST cada 60s
- 🔴 **Partial Fills no manejados**: Si orden se llena parcialmente, no se actualiza hasta próximo ciclo
- ⚠️ **SQLAlchemy sin optimistic locking**: Actualizaciones concurrentes pueden sobrescribirse

### 6. Reconciliación (cada 60s)

```python
# app/services/reconciliation_service.py:32
async def run_reconciliation_cycle(self):
    # 1. Obtiene balances de Binance
    account_info = client_singleton.get_account_info()

    # 2. Compara con BD interna (trades)
    # 3. Calcula discrepancia
    discrepancy = ext_usdt - int_usdt

    # 4. Activa breaker si supera umbral (1%)
    if relative_gap > self._threshold_pct:
        await self._breakers.activate_breaker('balance_discrepancy')
```

**Problemas**:
- 🔴 **Cálculo de discrepancia incorrecto** (LÍNEA: `reconciliation_service.py:80`):
  ```python
  int_total_value = total_value  # ⚠️ Usa el mismo valor que ext, no calcula desde BD
  discrepancy = 0.0  # Siempre 0!
  ```
- ⚠️ **No rastrea fills perdidos**: No compara trades de Binance vs trades internos

---

## 🔐 Seguridad y Autenticación

### API Key Management

```python
# app/core/config.py:21
binance_api_key: str = ""
binance_api_secret: str = ""

# ✅ Cargado desde .env
# ⚠️ NO usa secrets manager (Vault, AWS Secrets Manager)
```

**Problemas de Seguridad**:
1. 🔴 **Claves en variables de entorno**: Visibles en logs de Docker/k8s
2. 🔴 **Sin rotación automática**: API keys estáticas
3. 🔴 **Sin IP Whitelisting dinámico**: IPs permitidas hardcodeadas en Binance
4. ⚠️ **CORS permitiendo "*"** (LÍNEA: `main.py:197`):
   ```python
   allow_origins=["*"],  # ⚠️ Permitir todos los orígenes en producción
   ```

### Autenticación de Endpoints

```python
# app/core/auth.py
async def require_auth(api_key: str = Header(...)):
    expected = os.getenv("API_KEY")
    if api_key != expected:
        raise HTTPException(status_code=401)
```

**Problemas**:
- ⚠️ **Header API key en texto plano**: Sin HMAC ni firma
- ⚠️ **Sin rate limiting**: Vulnerable a brute force

---

## 🚨 Circuit Breakers

```python
# app/core/circuit_breakers.py:16
self.breakers = {
    'balance_discrepancy': {'active': False, ...},
    'operation_failure_rate': {'active': False, ...},
    'system_integrity': {'active': False, ...},
    'critical_mode': {'active': False, ...}
}
```

**Funcionamiento**:
- **Cooldown**: 5 minutos entre activaciones del mismo breaker
- **Edge-trigger**: Solo loggea cambios de estado
- **Métrica Prometheus**: `breaker_state{type="..."} 0|1`

**Problemas**:
- ⚠️ **Sin auto-recovery**: Breakers se activan pero no se desactivan automáticamente
- ⚠️ **Cooldown global**: No distingue entre errores transitorios y persistentes

---

## 🗄️ Persistencia y Concurrencia

### SQLAlchemy (Síncrono, no Async)

```python
# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
```

**Modelo de Trades**:
```python
# app/models/trade.py
class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    side = Column(String(10))
    quantity = Column(Numeric)
    price = Column(Numeric)
    status = Column(String(20))  # 'FILLED', 'PARTIALLY_FILLED', 'PENDING'
    binance_order_id = Column(String(50))
    client_order_id = Column(String(50), unique=True)
```

**Problemas Críticos de Concurrencia**:

1. 🔴 **Sin Optimistic Locking**:
   ```python
   # Scenario:
   # Thread A lee trade con status='PENDING'
   # Thread B lee trade con status='PENDING'
   # Thread A actualiza a 'FILLED'
   # Thread B sobrescribe con 'PENDING' (perdida de actualización!)
   ```

2. 🔴 **Sin Transaction Isolation explícito**: Usa nivel por defecto de PostgreSQL (READ COMMITTED)

3. 🔴 **Actualización de Balance no atómica**:
   ```python
   # app/services/balance_updater.py
   current_balance = db.query(...).first()
   new_balance = current_balance + quantity  # ⚠️ Read-Modify-Write sin lock
   db.update(..., balance=new_balance)
   ```

**Solución Recomendada**:
```python
# Agregar columna de versión
class Trade(Base):
    version = Column(Integer, default=0, nullable=False)

# Update con optimistic locking
stmt = update(Trade).where(
    Trade.id == trade_id,
    Trade.version == old_version
).values(
    status='FILLED',
    version=old_version + 1
)
result = session.execute(stmt)
if result.rowcount == 0:
    raise ConcurrentModificationError()
```

### Redis (Caché y Estado)

```python
# app/services/cache.py
_CACHE = get_async_cache()

# Usos:
# - Balances (TTL 300s)
# - Cycle State (TTL 600s)
# - Precision Cache (persistente)
```

**Problemas**:
- ⚠️ **Sin lock distribuido para tareas**: `SETNX` no usado
- ⚠️ **TTL muy cortos**: Balances con 5 minutos pueden desfasarse

---

## 📊 Observabilidad

### Métricas Prometheus

```python
# app/core/metrics.py
from prometheus_client import Counter, Gauge, Histogram

# Ejemplos:
gridbot_api_requests_total = Counter(...)
api_request_duration_seconds = Histogram(...)
portfolio_total_value_usdt = Gauge(...)
breaker_state = Gauge(..., labelnames=['type'])
```

**Endpoint**: `GET /metrics` (formato Prometheus text)

**Dashboards Grafana**:
- ROI Dashboard: `grafana-roi-dashboard.json`
- Circuit Breakers

**Problemas**:
- ⚠️ **Cardinality explosion risk**: Algunos labels con valores dinámicos (símbolos, orderIds)
- ⚠️ **Sin distributed tracing**: No hay trace_id propagado entre servicios

---

## 🛠️ Dependencias Externas

### Binance API

**Librerías usadas**:
1. `python-binance==1.0.19` (REST + WebSocket)
2. `unicorn-binance-websocket-api==1.45.0` (WebSocket alternativo)
3. `ccxt==4.1.77` (Trading genérico, no usado activamente)

**Rate Limits** (Binance Spot):
- REST: 1200 requests/minuto (weight-based)
- WebSocket: ilimitado (pero con keep-alive cada 30min)

**Problemas**:
- 🔴 **Sin circuit breaker para rate limits**: No detecta HTTP 429 y espera
- 🔴 **Sin exponential backoff**: Reintentos inmediatos
- ⚠️ **3 librerías de Binance**: Confusión y overhead

### PostgreSQL

**Versión**: 16.11 (Alpine)
**Usuarios**:
- `griduser`: Owner de BD `gridbot` (app)
- `grafana`: Owner de BD `grafana` (monitoring)

**Problemas**:
- ⚠️ **Sin réplica**: SPOF para lecturas
- ⚠️ **Sin backup automático**: No hay `pg_dump` periódico

---

## 🚦 Recomendaciones de Arquitectura

### Prioridad Alta (Riesgo Financiero)

1. **Implementar Optimistic Locking en Trades**
   - Agregar columna `version` a todas las tablas críticas
   - Usar `WHERE version = ?` en updates

2. **Lock Distribuido para Celery Tasks**
   ```python
   from redis import Redis
   redis = Redis()

   def trading_cycle_tick():
       lock = redis.lock("cycle_lock", timeout=300)
       if not lock.acquire(blocking=False):
           return  # Ciclo ya corriendo
       try:
           # ... lógica
       finally:
           lock.release()
   ```

3. **WebSocket para Order Fills**
   - Implementar listener de `executionReport`
   - Actualizar trades en tiempo real (no esperar 60s)

### Prioridad Media (Resiliencia)

4. **Migrar a asyncpg** (SQLAlchemy 2.0 async)
   ```python
   from sqlalchemy.ext.asyncio import create_async_engine
   engine = create_async_engine("postgresql+asyncpg://...")
   ```

5. **Exponential Backoff para Binance**
   ```python
   from tenacity import retry, wait_exponential

   @retry(wait=wait_exponential(min=1, max=60))
   def call_binance_api():
       ...
   ```

6. **Soft/Hard Time Limits en Celery**
   ```python
   @celery_app.task(soft_time_limit=240, time_limit=300)
   def trading_cycle_tick():
       ...
   ```

### Prioridad Baja (Mejoras)

7. **Secrets Manager** (Vault/AWS Secrets)
8. **Distributed Tracing** (OpenTelemetry + Jaeger)
9. **Rate Limiting** (slowapi + Redis)

---

## 📝 Changelog

| Fecha      | Cambio                                      | Auditor |
|------------|---------------------------------------------|---------|
| 2026-01-02 | Documento inicial post-auditoría profunda  | SA Team |
