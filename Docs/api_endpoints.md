# GridBot v2.5 - API Endpoints Técnicos

> **Última actualización**: 2026-01-02  
> **Auditor**: Senior Software Architect  
> **Versión**: 2.5.0

## 📑 Tabla de Contenidos

- [Autenticación](#autenticación)
- [Trading](#trading)
- [Integridad](#integridad)
- [Métricas y Monitoreo](#métricas-y-monitoreo)
- [Reconciliación](#reconciliación)
- [Circuit Breakers](#circuit-breakers)
- [Estrategias](#estrategias)
- [Portfolio](#portfolio)

---

## 🔐 Autenticación

### Método de Autenticación

**Header**: `X-API-Key`  
**Valor**: Configurado en variable de entorno `API_KEY`

```python
# app/core/auth.py:5
async def require_auth(api_key: str = Header(None, alias="X-API-Key")):
    expected_key = os.getenv("API_KEY")
    if not api_key or api_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return api_key
```

**Ejemplo de uso**:
```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api.gridbot.com/api/trades
```

**⚠️ Problemas de Seguridad**:
1. **Sin rate limiting**: Vulnerable a brute force
2. **Sin HMAC**: API key en texto plano
3. **Sin expiración**: Keys estáticas sin rotación

---

## 🎯 Trading

### `POST /api/trade/execute`

**Descripción**: Ejecuta una orden de trading manual con validaciones completas.

**Autenticación**: Requerida (`X-API-Key`)

**Request Body**:
```json
{
  "symbol": "ETHUSDT",
  "side": "BUY",
  "quantity": 0.01,
  "order_type": "MARKET",
  "price": null,
  "strategy": "manual"
}
```

**Response (200)**:
```json
{
  "status": "success",
  "order_id": "BIN-12345678",
  "client_order_id": "GRID-1704196800-ABC123",
  "symbol": "ETHUSDT",
  "side": "BUY",
  "quantity": 0.01,
  "executed_qty": 0.01,
  "price": 2345.67,
  "commission": 0.00001,
  "commission_asset": "ETH",
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**Errores Comunes**:
- `400`: Validación fallida (quantity < MIN_NOTIONAL, balance insuficiente)
- `401`: No autenticado
- `500`: Error de Binance API (rate limit, network)
- `503`: Circuit breaker activo

**Flujo Interno**:
```python
# app/api/trade.py:45
@router.post("/execute")
async def execute_trade(request: TradeRequest, api_key: str = Depends(require_auth)):
    # 1. Validar símbolo contra exchange_info
    validator = OrderValidator(client)
    validator.validate_order(...)
    
    # 2. Consultar circuit breakers
    if breakers.is_breaker_active('system_integrity'):
        raise HTTPException(503, "Trading disabled by circuit breaker")
    
    # 3. Ejecutar orden en Binance
    order = client.create_order(
        symbol=symbol,
        side=side,
        type='MARKET',
        quantity=quantity,
        newClientOrderId=f"GRID-{int(time.time())}-{uuid4().hex[:6]}"
    )
    
    # 4. Registrar en BD
    trade = Trade(...)
    db.add(trade)
    db.commit()
    
    # 5. Actualizar métricas Prometheus
    orders_executed_total.labels(symbol=symbol, side=side).inc()
    
    return order
```

**🔴 Problemas Identificados**:
- **Race Condition**: Entre validación de balance y ejecución
- **Sin retry**: Fallo de red no se reintenta automáticamente
- **Sin timeout**: Request puede colgar indefinidamente

---

### `GET /api/balances`

**Descripción**: Obtiene balances actuales de Binance (con caché de 5 minutos).

**Autenticación**: Requerida

**Response (200)**:
```json
{
  "USDT": {
    "free": 100.50,
    "locked": 0.0,
    "total": 100.50
  },
  "ETH": {
    "free": 0.05,
    "locked": 0.01,
    "total": 0.06
  },
  "BTC": {
    "free": 0.0001,
    "locked": 0.0,
    "total": 0.0001
  },
  "timestamp": "2026-01-02T20:00:00Z",
  "cached": true
}
```

**Caché**:
```python
# app/services/cache.py
BALANCES_TTL = 300  # 5 minutos
```

**⚠️ Problema**: TTL de 5 min puede mostrar datos obsoletos en trading activo.

---

### `GET /api/trades`

**Descripción**: Lista de trades históricos (filtrable).

**Query Parameters**:
- `symbol` (opcional): Filtrar por símbolo (ej: "ETHUSDT")
- `limit` (default: 50, max: 500): Cantidad de trades
- `start_time` (opcional): Timestamp Unix inicio
- `end_time` (opcional): Timestamp Unix fin

**Response (200)**:
```json
{
  "trades": [
    {
      "id": 123,
      "symbol": "ETHUSDT",
      "side": "BUY",
      "quantity": 0.01,
      "price": 2345.67,
      "commission": 0.00001,
      "status": "FILLED",
      "binance_order_id": "12345678",
      "client_order_id": "GRID-1704196800-ABC123",
      "created_at": "2026-01-02T20:00:00Z",
      "updated_at": "2026-01-02T20:00:05Z"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 50
}
```

**Queries SQL**:
```sql
SELECT * FROM trades
WHERE symbol = %s
  AND created_at >= %s
  AND created_at <= %s
ORDER BY created_at DESC
LIMIT %s;
```

**🔴 Problema**: Sin índice compuesto en `(symbol, created_at)` → Query lenta con muchos trades.

---

## 🛡️ Integridad

### `GET /integrity/status`

**Descripción**: Estado general de integridad del sistema.

**Autenticación**: No requerida (endpoint público de health)

**Response (200)**:
```json
{
  "status": "healthy",
  "overall_integrity_score": 95.5,
  "balance_validation": {
    "last_validation": "2026-01-02T19:59:30Z",
    "integrity_score": 98.0,
    "total_discrepancies": 1,
    "major_discrepancies": 0,
    "minor_discrepancies": 1
  },
  "operation_tracking": {
    "total_operations": 150,
    "successful_operations": 148,
    "failed_operations": 2,
    "success_rate": 0.9867
  },
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**Estados Posibles**:
- `healthy`: Score > 90
- `degraded`: Score 70-90
- `critical`: Score < 70

**Implementación**:
```python
# app/main.py:292
@app.get("/integrity/status")
async def get_integrity_status():
    balance_summary = await balance_validator.get_validation_summary()
    operation_summary = await operation_tracker.get_operation_summary()
    
    balance_integrity = balance_summary.get('integrity_score', 0)
    operation_integrity = operation_summary.get('success_rate', 0) * 100
    
    overall_integrity = (balance_integrity + operation_integrity) / 2
    
    return {
        "status": "healthy" if overall_integrity > 90 else "degraded" if overall_integrity > 70 else "critical",
        "overall_integrity_score": overall_integrity,
        ...
    }
```

---

### `POST /integrity/validate-balances`

**Descripción**: Forzar validación inmediata de balances contra Binance.

**Autenticación**: Requerida

**Response (200)**:
```json
{
  "message": "Validación de balances forzada exitosamente",
  "validation_result": {
    "discrepancies_found": 1,
    "assets_checked": 5,
    "integrity_score": 98.0,
    "details": [
      {
        "asset": "USDT",
        "internal_balance": 100.50,
        "binance_balance": 100.52,
        "diff": 0.02,
        "diff_pct": 0.02
      }
    ]
  },
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**Casos de Uso**:
- Post-trade verification
- Manual audit trigger
- Debug de discrepancias

---

### `GET /integrity/balances/discrepancies`

**Descripción**: Obtiene discrepancias actuales de balances.

**Autenticación**: Requerida

**Response (200)**:
```json
{
  "validation_summary": {
    "total_assets": 5,
    "discrepancies": [
      {
        "asset": "USDT",
        "internal": 100.50,
        "binance": 100.52,
        "diff": 0.02,
        "severity": "minor"
      }
    ],
    "major_count": 0,
    "minor_count": 1
  },
  "integrity_score": 98.0,
  "last_validation": "2026-01-02T19:59:30Z",
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**Severidad**:
- `critical`: diff > 5% o > $50
- `major`: diff > 1% o > $10
- `minor`: diff < 1% y < $10

---

### `POST /integrity/auto-correct-balance`

**Descripción**: Corrección automática de discrepancia (ajusta BD interna a Binance).

**Autenticación**: Requerida

**⚠️ WARNING**: Esta operación modifica directamente la contabilidad interna.

**Response (200)**:
```json
{
  "status": "success",
  "message": "Balance del sistema corregido automáticamente",
  "correction_details": {
    "asset": "USDT",
    "old_balance": 100.50,
    "new_balance": 100.52,
    "adjusted_by": 0.02,
    "reason": "auto_reconciliation"
  },
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**🔴 Riesgo**: Puede ocultar pérdidas reales si la discrepancia es por orden fallida no registrada.

---

## 📊 Métricas y Monitoreo

### `GET /metrics`

**Descripción**: Endpoint Prometheus con métricas en formato text.

**Autenticación**: No requerida (scrapeado por Prometheus)

**Response (200)**:
```
# HELP gridbot_api_requests_total Total de requests HTTP
# TYPE gridbot_api_requests_total counter
gridbot_api_requests_total{method="GET",endpoint="/api/balances",status="200"} 1523

# HELP api_request_duration_seconds Latencia de requests
# TYPE api_request_duration_seconds histogram
api_request_duration_seconds_bucket{method="GET",endpoint="/api/balances",le="0.1"} 1450
api_request_duration_seconds_bucket{method="GET",endpoint="/api/balances",le="0.5"} 1520
...

# HELP portfolio_total_value_usdt Valor total del portfolio en USDT
# TYPE portfolio_total_value_usdt gauge
portfolio_total_value_usdt{strategy="grid"} 256.78

# HELP breaker_state Estado de circuit breakers
# TYPE breaker_state gauge
breaker_state{type="balance_discrepancy"} 0
breaker_state{type="system_integrity"} 0
```

**Middleware**:
```python
# app/core/middleware/prometheus_http.py:15
class PrometheusHTTPMiddleware:
    async def __call__(self, scope, receive, send):
        start = time.time()
        # ... process request
        duration = time.time() - start
        api_request_duration_seconds.labels(
            method=scope['method'],
            endpoint=scope['path']
        ).observe(duration)
```

---

### `GET /api/metrics/portfolio`

**Descripción**: Métricas detalladas del portfolio (JSON).

**Autenticación**: Requerida

**Response (200)**:
```json
{
  "portfolio_value_usdt": 256.78,
  "cash_usdt": 100.52,
  "assets_value_usdt": 156.26,
  "total_pnl_usdt": 6.78,
  "total_pnl_pct": 2.71,
  "daily_pnl_usdt": 1.23,
  "positions": [
    {
      "asset": "ETH",
      "quantity": 0.05,
      "avg_entry_price": 2300.00,
      "current_price": 2345.67,
      "unrealized_pnl_usdt": 2.28,
      "unrealized_pnl_pct": 1.98
    }
  ],
  "timestamp": "2026-01-02T20:00:00Z"
}
```

---

## 🔄 Reconciliación

### `GET /api/reconciliation/summary`

**Descripción**: Resumen simple de última reconciliación con Binance.

**Autenticación**: No requerida

**Response (200)**:
```json
{
  "status": "ok",
  "cash_usdt": 100.52,
  "portfolio_total_usdt": 256.78,
  "valued_count": 4,
  "unvalued_count": 0,
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**🔴 Problema Crítico** (línea `main.py:519`):
```python
# ⚠️ Hace llamada SÍNCRONA a Binance en handler async!
acct = client_singleton.client.get_account()  # Blocking I/O
```

---

## 🚨 Circuit Breakers

### `GET /breakers/summary`

**Descripción**: Estado de todos los circuit breakers.

**Autenticación**: No requerida

**Response (200)**:
```json
{
  "breakers": {
    "balance_discrepancy": {
      "active": false,
      "activated_at": null,
      "reason": null
    },
    "operation_failure_rate": {
      "active": false,
      "activated_at": null,
      "reason": null
    },
    "system_integrity": {
      "active": true,
      "activated_at": "2026-01-02T19:55:00Z",
      "reason": "Binance API rate limit exceeded"
    },
    "critical_mode": {
      "active": false,
      "activated_at": null,
      "reason": null
    }
  },
  "total_active": 1,
  "critical_mode_enabled": false,
  "timestamp": "2026-01-02T20:00:00Z"
}
```

### `POST /breakers/activate`

**Descripción**: Activar circuit breaker manualmente.

**Autenticación**: Requerida

**Request Body**:
```json
{
  "breaker_type": "system_integrity",
  "reason": "Manual activation for maintenance"
}
```

**Response (200)**:
```json
{
  "status": "success",
  "message": "Circuit breaker 'system_integrity' activado",
  "timestamp": "2026-01-02T20:00:00Z"
}
```

### `POST /breakers/deactivate`

**Descripción**: Desactivar circuit breaker.

**Request Body**:
```json
{
  "breaker_type": "system_integrity"
}
```

---

## 🎲 Estrategias

### `GET /api/strategies`

**Descripción**: Lista de estrategias disponibles.

**Autenticación**: Requerida

**Response (200)**:
```json
{
  "strategies": [
    {
      "name": "GridTrading",
      "description": "Compra/venta en grid de precios",
      "risk_level": "medium",
      "min_confidence": 0.50,
      "supported_symbols": ["ETHUSDT", "BTCUSDT"]
    },
    {
      "name": "Scalping",
      "description": "Trading de alta frecuencia con spreads pequeños",
      "risk_level": "high",
      "min_confidence": 0.70,
      "supported_symbols": ["ETHUSDT"]
    },
    {
      "name": "RSI_MACD",
      "description": "Basado en indicadores técnicos",
      "risk_level": "low",
      "min_confidence": 0.60,
      "supported_symbols": ["ETHUSDT", "BTCUSDT", "BNBUSDT"]
    }
  ]
}
```

---

## 💼 Portfolio

### `GET /api/positions`

**Descripción**: Posiciones abiertas actuales.

**Autenticación**: Requerida

**Response (200)**:
```json
{
  "positions": [
    {
      "symbol": "ETHUSDT",
      "side": "LONG",
      "entry_price": 2300.00,
      "current_price": 2345.67,
      "quantity": 0.05,
      "value_usdt": 117.28,
      "unrealized_pnl_usdt": 2.28,
      "unrealized_pnl_pct": 1.98,
      "opened_at": "2026-01-01T15:30:00Z"
    }
  ],
  "total_positions": 1,
  "total_value_usdt": 117.28,
  "total_unrealized_pnl_usdt": 2.28,
  "timestamp": "2026-01-02T20:00:00Z"
}
```

---

## 🚦 Health Checks

### `GET /health`

**Descripción**: Health check simple para Docker/k8s.

**Autenticación**: No requerida

**Response (200)**:
```json
{
  "status": "ok",
  "timestamp": "2026-01-02T20:00:00Z"
}
```

**Usado por**:
- Docker healthcheck
- Kubernetes liveness probe
- Load balancer health check

---

## 🔧 Decoradores FastAPI Detectados

### Router Prefix Patterns

```python
# app/api/trade.py
router = APIRouter(prefix="/api/trade", tags=["trading"])

# app/api/metrics.py
router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# app/api/integrity_routes.py
router = APIRouter(prefix="/integrity", tags=["integrity"])
```

### Dependency Injection

```python
# Autenticación
@router.get("/protected")
async def protected_endpoint(api_key: str = Depends(require_auth)):
    ...

# Database Session
@router.get("/data")
async def get_data(db: Session = Depends(get_db)):
    ...

# Circuit Breakers
@router.post("/trade")
async def trade(breakers: CircuitBreakers = Depends(get_breakers)):
    ...
```

---

## 📝 Problemas y Mejoras

### Críticos (P0)

1. **Race Conditions en Balance**: Validación y ejecución no son atómicas
2. **Blocking I/O en endpoints async**: `client.get_account()` en `/api/reconciliation/summary`
3. **Sin índices en queries**: Tabla `trades` sin índice compuesto

### Altos (P1)

4. **CORS permitiendo "*"**: Riesgo de CSRF
5. **Sin rate limiting**: Vulnerable a DoS
6. **Sin retry en llamadas Binance**: Fallos transitorios no se manejan

### Medios (P2)

7. **Caché de balances con TTL 5min**: Puede mostrar datos obsoletos
8. **Sin paginación server-side**: `/api/trades` puede retornar miles de registros
9. **Sin compression**: Responses grandes sin gzip

### Bajos (P3)

10. **Sin HATEOAS**: No hay links a recursos relacionados
11. **Sin API versioning**: Futuros cambios breaking afectarán clientes
12. **Sin OpenAPI 3.1**: Spec es 3.0.x

---

## 📚 Referencias

- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [REST API Design Guide](https://restfulapi.net/)
- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)


