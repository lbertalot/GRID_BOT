# GridBot v2.5 - Roadmap de Evolución

> **Fecha de Auditoría**: 2026-01-02
> **Auditor**: Senior Software Architect & Security Lead
> **Horizon**: Q1-Q2 2026

---

## 🎯 Executive Summary

Este roadmap prioriza mejoras críticas identificadas durante la auditoría exhaustiva del codebase. Las prioridades se basan en:

1. **Riesgo Financiero**: Problemas que pueden causar pérdida de dinero
2. **Estabilidad del Sistema**: Race conditions y concurrencia
3. **Seguridad**: Vulnerabilidades de API y manejo de secretos
4. **Performance**: Optimizaciones de latencia y throughput
5. **Features**: Nuevas capacidades de trading

---

## 🔴 **FASE 1: Critical Fixes (Semana 1-2)**

### ❗ Issue #1: Race Conditions en Balance Updates

**Problema** (`app/services/balance_updater.py:~40`):
```python
# Thread A lee balance
current_balance = db.query(Balance).filter_by(asset="USDT").first()
# Thread B lee el mismo balance
# Thread A actualiza
current_balance.amount += 10
db.commit()
# Thread B actualiza (sobrescribe cambio de A)
current_balance.amount += 5
db.commit()  # ⚠️ Pérdida de actualización!
```

**Solución**:
```python
# 1. Agregar columna de versión
class Balance(Base):
    __tablename__ = "balances"
    id = Column(Integer, primary_key=True)
    asset = Column(String(20), unique=True)
    amount = Column(Numeric(20, 8))
    version = Column(Integer, default=0, nullable=False)  # ✅ NUEVO

# 2. Update con optimistic locking
from sqlalchemy import update

def update_balance_atomic(asset, delta):
    old_balance = db.query(Balance).filter_by(asset=asset).first()
    old_version = old_balance.version

    stmt = update(Balance).where(
        Balance.asset == asset,
        Balance.version == old_version  # ✅ Verificar versión
    ).values(
        amount=Balance.amount + delta,
        version=old_version + 1  # ✅ Incrementar versión
    )

    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        # Otra transacción modificó el balance
        raise ConcurrentModificationError("Balance was modified, retry")

    return result
```

**Archivos a Modificar**:
- `app/models/trade.py`: Agregar `version` column
- `app/services/balance_updater.py`: Usar optimistic locking
- `alembic/versions/`: Crear migración para agregar `version`

**Test**:
```python
# tests/test_concurrent_balance.py
def test_concurrent_balance_updates():
    # Simular 10 threads actualizando mismo balance
    threads = []
    for i in range(10):
        t = Thread(target=lambda: update_balance_atomic("USDT", 1.0))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    final_balance = db.query(Balance).filter_by(asset="USDT").first()
    assert final_balance.amount == initial + 10.0  # ✅ Sin pérdidas
```

**Impacto**: **CRÍTICO** - Previene pérdida de fondos por race condition
**Esfuerzo**: 8 horas (1 día)
**Responsable**: Backend Lead

---

### ❗ Issue #2: Lock Distribuido para Celery Tasks

**Problema** (`app/services/trading_tasks.py:101`):
```python
@celery_app.task
def trading_cycle_tick():
    # Sin lock, si tarea anterior no terminó, se ejecuta en paralelo
    # ⚠️ Doble ejecución de órdenes!
```

**Solución**:
```python
from redis import Redis
from redis.lock import Lock

redis_client = Redis.from_url(os.getenv("REDIS_URL"))

@celery_app.task
def trading_cycle_tick():
    lock = redis_client.lock(
        name="trading_cycle_lock",
        timeout=300,  # 5 minutos max
        blocking=False  # No esperar si ya está locked
    )

    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.warning("🔒 Trading cycle ya en ejecución, omitiendo")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        # ... lógica de trading
        result = execute_cycle()
        return result
    finally:
        try:
            lock.release()
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
```

**Archivos a Modificar**:
- `app/services/trading_tasks.py`: Agregar lock distribuido
- `app/services/rebalancing_tasks.py`: Idem
- `app/services/ml_tasks.py`: Idem

**Test**:
```python
def test_trading_cycle_lock():
    # Ejecutar 2 tareas en paralelo
    task1 = trading_cycle_tick.apply_async()
    task2 = trading_cycle_tick.apply_async()

    result1 = task1.get()
    result2 = task2.get()

    # Una debe ejecutarse, otra debe ser skipped
    statuses = [result1['status'], result2['status']]
    assert "ok" in statuses
    assert "skipped" in statuses
```

**Impacto**: **CRÍTICO** - Previene doble trading y pérdidas
**Esfuerzo**: 4 horas
**Responsable**: Backend Lead

---

### ❗ Issue #3: WebSocket para Order Fills en Tiempo Real

**Problema**: Sistema depende de polling REST cada 60s para actualizar fills.

**Solución**:
```python
# app/services/binance_user_stream.py (mejorado)
import asyncio
import aiohttp
from typing import Callable

class BinanceUserStreamHandler:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._session = None
        self._listen_key = None
        self._ws = None
        self._running = False

    async def start(self, on_fill: Callable):
        """Iniciar listener de userDataStream"""
        self._session = aiohttp.ClientSession()

        # 1. Crear listen key
        self._listen_key = await self._create_listen_key()

        # 2. Conectar a WebSocket
        ws_url = f"wss://stream.binance.com:9443/ws/{self._listen_key}"
        self._ws = await self._session.ws_connect(ws_url)

        # 3. Listener loop
        self._running = True
        asyncio.create_task(self._listen_loop(on_fill))
        asyncio.create_task(self._keepalive_loop())

    async def _listen_loop(self, on_fill):
        """Procesar mensajes de WebSocket"""
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = msg.json()
                event_type = data.get("e")

                if event_type == "executionReport":
                    # Order fill detected!
                    order_status = data.get("X")  # FILLED, PARTIALLY_FILLED

                    if order_status in ["FILLED", "PARTIALLY_FILLED"]:
                        fill_data = {
                            "symbol": data.get("s"),
                            "side": data.get("S"),
                            "order_id": data.get("i"),
                            "client_order_id": data.get("c"),
                            "price": float(data.get("p")),
                            "quantity": float(data.get("q")),
                            "executed_qty": float(data.get("z")),
                            "status": order_status,
                            "timestamp": data.get("T")
                        }

                        # Callback para actualizar BD
                        await on_fill(fill_data)

    async def _keepalive_loop(self):
        """PUT listen_key cada 30 minutos"""
        while self._running:
            await asyncio.sleep(1800)  # 30 min
            try:
                await self._extend_listen_key()
            except Exception as e:
                logger.error(f"Error extending listen_key: {e}")

# app/main.py: Iniciar en lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ...
    # Iniciar WebSocket handler
    ws_handler = BinanceUserStreamHandler(api_key)
    await ws_handler.start(on_fill=handle_order_fill)
    yield
    await ws_handler.stop()

async def handle_order_fill(fill_data: Dict):
    """Callback cuando se detecta un fill"""
    logger.info(f"🎯 Fill detectado: {fill_data}")

    # Actualizar trade en BD
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter_by(
            client_order_id=fill_data["client_order_id"]
        ).first()

        if trade:
            trade.status = fill_data["status"]
            trade.executed_qty = fill_data["executed_qty"]
            trade.updated_at = datetime.now()
            db.commit()

            # Métricas
            orders_filled_total.labels(
                symbol=fill_data["symbol"],
                side=fill_data["side"]
            ).inc()
    finally:
        db.close()
```

**Archivos Nuevos**:
- `app/services/websocket_order_fills.py`: Handler de WebSocket
- `tests/test_websocket_fills.py`: Tests unitarios

**Archivos a Modificar**:
- `app/main.py`: Iniciar WebSocket en lifespan
- `app/services/trading_tasks.py`: Eliminar polling de fills

**Impacto**: **ALTO** - Reduce latencia de actualización de 60s a <1s
**Esfuerzo**: 16 horas (2 días)
**Responsable**: Backend Lead + DevOps

---

### ❗ Issue #4: Async SQLAlchemy (asyncpg)

**Problema**: SQLAlchemy actual es síncrono, bloquea event loop de FastAPI.

**Solución**:
```python
# app/db/session.py (reescribir)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20, max_overflow=0)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# app/api/trade.py (modificar)
@router.get("/trades")
async def get_trades(
    db: AsyncSession = Depends(get_db)  # ✅ Ahora async
):
    result = await db.execute(
        select(Trade).where(Trade.symbol == "ETHUSDT")
    )
    trades = result.scalars().all()
    return trades
```

**Archivos a Modificar** (Refactor Grande):
- `app/db/session.py`: Migrar a async
- `app/models/*.py`: Verificar compatibilidad
- `app/services/*.py`: Cambiar queries a async/await (50+ archivos)
- `app/api/*.py`: Cambiar endpoints a async/await
- `requirements.txt`: Agregar `asyncpg==0.29.0`

**Test**:
```python
@pytest.mark.asyncio
async def test_async_query_performance():
    start = time.time()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Trade).limit(1000))
        trades = result.scalars().all()
    elapsed = time.time() - start

    # Async debe ser más rápido que sync
    assert elapsed < 0.5  # < 500ms
```

**Impacto**: **ALTO** - Mejora throughput y latencia
**Esfuerzo**: 80 horas (2 semanas)
**Responsable**: Backend Team (2 devs)

---

## 🟠 **FASE 2: Seguridad y Resiliencia (Semana 3-4)**

### 🔒 Issue #5: Secrets Manager (HashiCorp Vault)

**Problema**: API keys en variables de entorno (visibles en logs/env).

**Solución**:
```python
# app/core/secrets_manager.py (NUEVO)
import hvac

class SecretsManager:
    def __init__(self):
        self.vault_url = os.getenv("VAULT_ADDR", "http://vault:8200")
        self.vault_token = os.getenv("VAULT_TOKEN")
        self.client = hvac.Client(url=self.vault_url, token=self.vault_token)

    def get_secret(self, path: str) -> Dict:
        """Obtener secreto de Vault"""
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response['data']['data']

    def get_binance_credentials(self) -> Tuple[str, str]:
        """Obtener credenciales de Binance"""
        secrets = self.get_secret("gridbot/binance")
        return secrets['api_key'], secrets['api_secret']

# app/services/binance_client_singleton.py (modificar)
def get_binance_client_singleton():
    if not hasattr(get_binance_client_singleton, "_instance"):
        secrets_manager = SecretsManager()
        api_key, api_secret = secrets_manager.get_binance_credentials()

        get_binance_client_singleton._instance = BinanceClientWrapper(
            api_key=api_key,
            api_secret=api_secret
        )

    return get_binance_client_singleton._instance
```

**Infraestructura**:
```yaml
# docker-compose.yml (agregar)
services:
  vault:
    image: vault:1.15
    container_name: gridbot_vault
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: "dev-token"
      VAULT_DEV_LISTEN_ADDRESS: "0.0.0.0:8200"
    cap_add:
      - IPC_LOCK
    volumes:
      - ./docker/vault:/vault/config
```

**Archivos a Modificar**:
- `app/core/secrets_manager.py`: NUEVO
- `app/services/binance_client_singleton.py`: Usar Secrets Manager
- `docker-compose.yml`: Agregar servicio Vault
- `requirements.txt`: Agregar `hvac==2.1.0`

**Impacto**: **ALTO** - Previene exposición de claves
**Esfuerzo**: 24 horas (3 días)
**Responsable**: DevOps + Security

---

### 🔒 Issue #6: Rate Limiting (slowapi + Redis)

**Problema**: No hay rate limiting, vulnerable a brute force y DoS.

**Solución**:
```python
# app/core/rate_limiter.py (NUEVO)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL")
)

# app/main.py
from app.core.rate_limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# app/api/trade.py
@router.post("/execute")
@limiter.limit("10/minute")  # ✅ Max 10 órdenes por minuto por IP
async def execute_trade(
    request: Request,  # ✅ Necesario para slowapi
    trade_data: TradeRequest
):
    ...
```

**Archivos a Modificar**:
- `app/core/rate_limiter.py`: NUEVO
- `app/main.py`: Configurar limiter
- `app/api/*.py`: Agregar decoradores `@limiter.limit`
- `requirements.txt`: Agregar `slowapi==0.1.9`

**Impacto**: **MEDIO** - Protege contra abuso
**Esfuerzo**: 8 horas (1 día)
**Responsable**: Backend Lead

---

### 🔒 Issue #7: IP Whitelisting Dinámico

**Problema**: IPs permitidas hardcodeadas en Binance, no se actualizan.

**Solución**:
```python
# app/services/ip_whitelist_manager.py (NUEVO)
import requests

class IPWhitelistManager:
    def __init__(self, binance_api_key, binance_api_secret):
        self.api_key = binance_api_key
        self.api_secret = binance_api_secret
        self.base_url = "https://api.binance.com"

    def get_current_public_ip(self) -> str:
        """Obtener IP pública actual"""
        response = requests.get("https://api.ipify.org")
        return response.text

    def update_binance_whitelist(self):
        """Actualizar whitelist de Binance con IP actual"""
        current_ip = self.get_current_public_ip()

        # Llamar a Binance API para actualizar whitelist
        # (requiere permisos especiales en API key)
        endpoint = "/sapi/v1/account/apiRestrictions"
        params = {
            "apiKey": self.api_key,
            "ipRestrict": True,
            "ipList": current_ip
        }

        # ... firma HMAC y llamada
        logger.info(f"✅ Whitelist actualizada con IP: {current_ip}")

# Tarea periódica (cada hora)
@celery_app.task
def update_ip_whitelist():
    manager = IPWhitelistManager(api_key, api_secret)
    manager.update_binance_whitelist()
```

**Archivos Nuevos**:
- `app/services/ip_whitelist_manager.py`: NUEVO
- `app/scheduler/ip_whitelist_job.py`: NUEVO (Celery Beat job)

**Impacto**: **MEDIO** - Mejora seguridad de API keys
**Esfuerzo**: 12 horas (1.5 días)
**Responsable**: DevOps

---

### 🔄 Issue #8: Exponential Backoff con Tenacity

**Problema**: Llamadas a Binance sin retry ante fallas transitorias.

**Solución**:
```python
# app/services/binance_client_singleton.py (modificar)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from binance.exceptions import BinanceAPIException

class BinanceClientWrapper:
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((requests.ConnectionError, BinanceAPIException)),
        reraise=True
    )
    def get_account_info(self):
        """Obtener info de cuenta con retry exponential"""
        return self.client.get_account()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        retry=retry_if_exception_type(requests.ConnectionError)
    )
    def create_order(self, **kwargs):
        """Crear orden con retry (menos agresivo que queries)"""
        return self.client.create_order(**kwargs)
```

**Archivos a Modificar**:
- `app/services/binance_client_singleton.py`: Agregar `@retry`
- `app/services/binance_async.py`: Idem
- `requirements.txt`: Ya tiene `tenacity==8.2.3` ✅

**Impacto**: **MEDIO** - Mejora resiliencia ante fallas de red
**Esfuerzo**: 4 horas
**Responsable**: Backend Lead

---

## 🟡 **FASE 3: Performance y Observabilidad (Semana 5-6)**

### ⚡ Issue #9: Redis Caching Layer Mejorado

**Problema**: Caché de balances con TTL 5min, no invalida en write.

**Solución**:
```python
# app/services/cache_manager.py (reescribir)
import redis
import json
from typing import Optional

class CacheManager:
    def __init__(self):
        self.redis = redis.Redis.from_url(os.getenv("REDIS_URL"))
        self.default_ttl = 300  # 5 minutos

    def get(self, key: str) -> Optional[Dict]:
        """Get de caché"""
        value = self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    def set(self, key: str, value: Dict, ttl: int = None):
        """Set en caché con TTL"""
        self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(value, default=str)
        )

    def delete(self, key: str):
        """Invalidar caché"""
        self.redis.delete(key)

    def get_or_compute(self, key: str, compute_fn: Callable, ttl: int = None):
        """Cache-aside pattern"""
        cached = self.get(key)
        if cached is not None:
            return cached

        # Compute value
        value = compute_fn()
        self.set(key, value, ttl)
        return value

# Uso en balance updates
def update_balance(asset: str, delta: Decimal):
    # 1. Actualizar BD
    balance = db.query(Balance).filter_by(asset=asset).first()
    balance.amount += delta
    db.commit()

    # 2. Invalidar caché
    cache_manager.delete(f"balance:{asset}")
    cache_manager.delete("balances:all")  # ✅ Invalidar agregado
```

**Archivos a Modificar**:
- `app/services/cache_manager.py`: Reescribir con invalidación
- `app/services/balance_updater.py`: Invalidar caché en updates
- `tests/test_cache_invalidation.py`: NUEVO

**Impacto**: **MEDIO** - Reduce queries innecesarias
**Esfuerzo**: 8 horas (1 día)
**Responsable**: Backend Lead

---

### 📊 Issue #10: Distributed Tracing (OpenTelemetry)

**Problema**: No hay trace_id propagado entre servicios.

**Solución**:
```python
# app/core/tracing.py (NUEVO)
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_tracing(app: FastAPI):
    # Configurar Jaeger
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "jaeger"),
        agent_port=6831,
    )

    # Configurar provider
    provider = TracerProvider()
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrumentar FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrumentar SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=engine)

    return trace.get_tracer(__name__)

# app/main.py
tracer = setup_tracing(app)

# Uso en servicios
@tracer.start_as_current_span("execute_trading_cycle")
def execute_trading_cycle():
    with tracer.start_as_current_span("fetch_market_data"):
        data = fetch_market_data()

    with tracer.start_as_current_span("ml_prediction"):
        prediction = ml_engine.predict(data)

    with tracer.start_as_current_span("place_order"):
        order = place_order(prediction)

    return order
```

**Infraestructura**:
```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: gridbot_jaeger
    ports:
      - "5775:5775/udp"
      - "6831:6831/udp"
      - "16686:16686"  # Jaeger UI
    environment:
      COLLECTOR_ZIPKIN_HTTP_PORT: 9411
```

**Archivos Nuevos**:
- `app/core/tracing.py`: NUEVO
- `docker/jaeger/`: Configs

**Archivos a Modificar**:
- `app/main.py`: Setup tracing
- `app/services/*.py`: Agregar spans
- `requirements.txt`: Agregar `opentelemetry-*`

**Impacto**: **MEDIO** - Facilita debug de latencias
**Esfuerzo**: 24 horas (3 días)
**Responsable**: DevOps + Backend

---

### 📊 Issue #11: Métricas de Cardinality Optimization

**Problema**: Labels de Prometheus con alta cardinality (symbols, orderIds).

**Solución**:
```python
# app/core/metrics.py (refactor)
from prometheus_client import Counter, Histogram, Gauge

# ❌ ANTES (alta cardinality)
orders_executed_total = Counter(
    "orders_executed_total",
    "Total de órdenes ejecutadas",
    labelnames=["symbol", "side", "strategy", "order_id"]  # ⚠️ order_id único!
)

# ✅ DESPUÉS (baja cardinality)
orders_executed_total = Counter(
    "orders_executed_total",
    "Total de órdenes ejecutadas",
    labelnames=["symbol", "side", "strategy"]  # ✅ Solo 3 labels
)

# Para métricas granulares, usar logs estructurados
import structlog
logger = structlog.get_logger()

def record_order_execution(order):
    # Métrica agregada
    orders_executed_total.labels(
        symbol=order.symbol,
        side=order.side,
        strategy=order.strategy
    ).inc()

    # Log granular con order_id
    logger.info(
        "order_executed",
        order_id=order.id,
        client_order_id=order.client_order_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price
    )
```

**Archivos a Modificar**:
- `app/core/metrics.py`: Reducir labels
- `app/services/*.py`: Usar structlog para detalles

**Impacto**: **MEDIO** - Reduce carga de Prometheus
**Esfuerzo**: 8 horas (1 día)
**Responsable**: DevOps

---

## 🟢 **FASE 4: Features y ML (Semana 7-8)**

### 🚀 Issue #12: Panic Sell Button (Emergency Exit)

**Problema**: No hay manera rápida de cerrar todas las posiciones.

**Solución**:
```python
# app/api/emergency.py (NUEVO)
@router.post("/emergency/panic-sell")
@limiter.limit("1/minute")  # Solo 1 por minuto
async def panic_sell(
    confirm: str,  # Requiere confirmación explícita
    api_key: str = Depends(require_auth)
):
    if confirm != "YES_SELL_ALL":
        raise HTTPException(400, "Confirmación requerida")

    logger.critical("🚨 PANIC SELL ACTIVADO 🚨")

    # 1. Activar circuit breaker crítico
    await breakers.activate_critical_mode()

    # 2. Obtener todas las posiciones abiertas
    positions = await get_all_open_positions()

    # 3. Crear órdenes de venta MARKET para todo
    results = []
    for pos in positions:
        try:
            order = client.create_order(
                symbol=pos.symbol,
                side="SELL",
                type="MARKET",
                quantity=pos.quantity
            )
            results.append({
                "symbol": pos.symbol,
                "status": "success",
                "order_id": order["orderId"]
            })
        except Exception as e:
            results.append({
                "symbol": pos.symbol,
                "status": "error",
                "error": str(e)
            })

    # 4. Enviar alerta Telegram
    await send_telegram_alert(
        f"🚨 PANIC SELL EJECUTADO\n"
        f"Posiciones cerradas: {len(results)}\n"
        f"Éxitos: {sum(1 for r in results if r['status'] == 'success')}"
    )

    return {
        "status": "completed",
        "results": results,
        "timestamp": datetime.now().isoformat()
    }
```

**Archivos Nuevos**:
- `app/api/emergency.py`: NUEVO
- `tests/test_emergency_exit.py`: NUEVO

**Impacto**: **ALTO** - Protección ante eventos extremos
**Esfuerzo**: 12 horas (1.5 días)
**Responsable**: Backend Lead

---

### 🤖 Issue #13: ML Model Monitoring (Evidently AI)

**Problema**: No hay métricas de performance de modelos ML.

**Solución**:
```python
# app/services/ml_monitoring.py (NUEVO)
from evidently.dashboard import Dashboard
from evidently.tabs import RegressionPerformanceTab

class MLMonitor:
    def __init__(self):
        self.dashboard = Dashboard(tabs=[RegressionPerformanceTab()])
        self.predictions = []
        self.actuals = []

    def log_prediction(self, features, prediction, actual=None):
        """Log predicción para monitoreo"""
        self.predictions.append({
            "timestamp": datetime.now(),
            "features": features,
            "prediction": prediction,
            "actual": actual
        })

    def calculate_model_metrics(self):
        """Calcular métricas de modelo"""
        if len(self.predictions) < 10:
            return

        predictions = [p["prediction"] for p in self.predictions]
        actuals = [p["actual"] for p in self.predictions if p["actual"] is not None]

        if len(actuals) > 0:
            from sklearn.metrics import mean_squared_error, mean_absolute_error

            mse = mean_squared_error(actuals, predictions[:len(actuals)])
            mae = mean_absolute_error(actuals, predictions[:len(actuals)])

            # Exportar como métricas Prometheus
            ml_prediction_error_mse.set(mse)
            ml_prediction_error_mae.set(mae)
```

**Archivos Nuevos**:
- `app/services/ml_monitoring.py`: NUEVO
- `requirements.txt`: Agregar `evidently==0.4.0`

**Impacto**: **BAJO** - Mejora confiabilidad de ML
**Esfuerzo**: 16 horas (2 días)
**Responsable**: ML Engineer

---

## 📅 **Timeline Summary**

| Fase   | Duración  | Esfuerzo Total | Prioridad |
|--------|-----------|----------------|-----------|
| Fase 1 | 2 semanas | 108 horas      | CRÍTICA   |
| Fase 2 | 2 semanas | 48 horas       | ALTA      |
| Fase 3 | 2 semanas | 40 horas       | MEDIA     |
| Fase 4 | 2 semanas | 28 horas       | BAJA      |
| **TOTAL** | **8 semanas** | **224 horas** | - |

---

## 👥 **Team Allocation**

- **Backend Lead** (1 FTE): Issues #1, #2, #3, #6, #8, #9, #12
- **Backend Dev** (1 FTE): Issue #4 (async SQLAlchemy)
- **DevOps** (0.5 FTE): Issues #5, #7, #10, #11
- **ML Engineer** (0.5 FTE): Issue #13

---

## 🎯 **Success Metrics**

| Métrica                        | Baseline | Target | ¿Cómo medir?                |
|--------------------------------|----------|--------|-----------------------------|
| Race conditions detectadas     | 0        | 0      | Tests concurrentes pasan    |
| Latencia P99 API               | 450ms    | <250ms | Prometheus histogram        |
| Órdenesdobles/semana           | 2        | 0      | Logs de lock skipped        |
| Balance discrepancies/día      | 3        | <1     | Reconciliation metrics      |
| Secrets en .env                | 4        | 0      | Vault audit                 |
| Failed Binance calls (network) | 5%       | <1%    | Retry success rate          |

---

## 📚 **Referencias Técnicas**

- [Optimistic Locking in SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/versioning.html)
- [Redis Distributed Locks](https://redis.io/docs/manual/patterns/distributed-locks/)
- [Binance WebSocket API](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams)
- [FastAPI Performance Best Practices](https://fastapi.tiangolo.com/deployment/concepts/)
- [OpenTelemetry Python](https://opentelemetry-python.readthedocs.io/)

---

**FIN DEL ROADMAP**
