# GridBot v2.5 — Contratos entre Módulos

## Propósito
Define los contratos formales entre los módulos principales del sistema.
Todo cambio en un módulo DEBE respetar los contratos definidos aquí.

---

## CTR-001: OrderValidator

**Módulo:** `app/services/order_validation.py`

**Contrato de entrada:**
```python
def validate_order_parameters(
    symbol: str,           # Par de trading (e.g., "BTCUSDT")
    quantity: Decimal,     # Cantidad deseada (Decimal, NUNCA float)
    side: str,             # "BUY" | "SELL"
    order_type: str,       # "MARKET" | "LIMIT"
    price: Optional[Decimal] = None  # Precio para LIMIT (Decimal)
) -> Dict[str, Any]
```

**Contrato de salida:**
```python
{
    "is_valid": bool,
    "errors": List[str],           # Lista de errores (vacía si válido)
    "warnings": List[str],         # Advertencias (no bloqueantes)
    "quantity_info": {
        "original_quantity": Decimal,
        "adjusted_quantity": Decimal,  # Ajustada a stepSize
        "step_size": Decimal,
        "min_qty": Decimal,
        "max_qty": Decimal,
        "min_notional": Decimal,
    },
    "current_price": Decimal,
    "adjusted_price": Optional[Decimal],  # Ajustado a tickSize (LIMIT)
    "notional_value": Decimal,
    "recommended_quantity": Decimal,
}
```

**Invariantes garantizadas:**
- `adjusted_quantity` siempre es múltiplo de `stepSize`.
- `adjusted_price` (si LIMIT) siempre es múltiplo de `tickSize`.
- `notional_value >= minNotional` si `is_valid == True`.
- Todos los valores monetarios son `Decimal`.

---

## CTR-002: TradeExecutor

**Módulo:** `app/services/trade_executor.py`

**Contrato de entrada:**
```python
async def execute_order(
    symbol: str,
    side: str,              # "BUY" | "SELL"
    order_type: str,        # "MARKET" | "LIMIT"
    quantity: Decimal,      # Ya validada por OrderValidator
    price: Optional[Decimal] = None,
    client_order_id: Optional[str] = None,
) -> Dict[str, Any]
```

**Precondiciones (MUST):**
1. `CircuitBreakers.is_trading_halted()` == False
2. `OrderValidator.validate_order_parameters()` == `is_valid: True`
3. Balance suficiente verificado
4. `client_order_id` proporcionado o generado internamente

**Contrato de salida:**
```python
{
    "order_id": int,
    "client_order_id": str,
    "status": str,           # "FILLED" | "PARTIALLY_FILLED" | "NEW" | "REJECTED"
    "executed_qty": Decimal,
    "avg_price": Decimal,
    "commission": Decimal,
    "raw_response": Dict,    # Respuesta cruda de Binance
}
```

**Postcondiciones:**
- Si `status == "FILLED"`: balances internos actualizados.
- Si `status == "PARTIALLY_FILLED"`: balances parcialmente actualizados, operación tracked.
- Si falla: excepción propagada, ningún balance modificado.

---

## CTR-003: ReconciliationService

**Módulo:** `app/services/reconciliation_service.py`

**Contrato:**
```python
async def run_reconciliation_cycle() -> Dict[str, Any]
```

**Salida:**
```python
{
    "status": "ok" | "error",
    "ext_usdt": Decimal,              # Balance USDT en exchange
    "portfolio_total_usdt": Decimal,  # Valor total del portfolio en USDT
    "int_usdt": Decimal,              # Balance USDT interno
    "discrepancy_usd": Decimal,       # Discrepancia absoluta
    "discrepancy_pct": Decimal,       # Discrepancia relativa
    "latency_seconds": float,         # Latencia del ciclo
}
```

**Invariantes:**
- Se ejecuta cada ≤ 60 segundos.
- Activa breaker si `discrepancy_pct > threshold_pct`.
- Registra latencia en `reconciliation_latency_seconds`.
- Registra discrepancia en `balance_discrepancy_usd`.

---

## CTR-004: CircuitBreakers

**Módulo:** `app/core/circuit_breakers.py`

**Contrato:**
```python
# Consulta (sync, sin I/O)
def is_trading_halted() -> bool
def is_breaker_active(breaker_type: str) -> bool
def is_critical_mode_active() -> bool

# Activación (async)
async def activate_breaker(breaker_type: str, reason: str) -> bool
async def deactivate_breaker(breaker_type: str) -> bool
async def activate_critical_mode() -> bool
```

**Tipos de breakers:**
- `balance_discrepancy`: discrepancia de balance > umbral
- `operation_failure_rate`: tasa de fallos > umbral
- `system_integrity`: problemas de integridad del sistema
- `critical_mode`: modo crítico total

**Invariantes:**
- `is_trading_halted()` es O(1), sin I/O.
- Si `critical_mode` está activo, TODOS los breakers están activos.
- Cooldown configurable para evitar flapping.

---

## CTR-005: RiskManager (core)

**Módulo:** `app/core/risk_manager.py`

**Contrato principal:**
```python
def calculate_dynamic_position_size(params: PositionSizeParams) -> float
```

Donde `PositionSizeParams`:
```python
@dataclass
class PositionSizeParams:
    symbol: str
    account_equity: float
    atr: float
    winrate_estimate: float
    avg_win_loss_ratio: float
    price: float
    risk_per_trade_pct: float = 0.02
    cap_symbol_pct: float = 0.20
    cap_equity_pct: float = 0.80
    cap_daily_loss_pct: float = 0.05
```

**Invariantes:**
- Resultado siempre > 0 y <= `account_equity * cap_equity_pct`.
- Kelly fraccional solo se usa si `winrate > 0.5` y `avg_win_loss_ratio > 1.0`.
- Fallback a ATR-based sizing si Kelly no es aplicable.
- Multiplicador de régimen de mercado siempre aplicado.

---

## CTR-006: StrategySelector

**Módulo:** `app/services/strategy_selector.py`

**Contrato:**
```python
def select_strategy(
    regime_prediction: RegimePrediction,
    symbol: str,
    account_state: AccountState
) -> StrategySpec
```

**Invariantes:**
- Si `emergency_stop` está activo, retorna `StrategyType.HOLD`.
- Si el régimen no tiene config, retorna `StrategyType.HOLD`.
- `confidence` siempre está en `[0.0, 1.0]`.
- Nunca selecciona estrategia agresiva con `risk_score > 0.8`.

---

## CTR-007: IntegrityGuardMiddleware

**Módulo:** `app/core/middleware/integrity_guard.py`

**Contrato:**
- Intercepta POST/PUT/DELETE en rutas protegidas.
- Si hay breakers activos, retorna HTTP 503 con detalle de breakers.
- Rutas de lectura (GET/HEAD/OPTIONS) siempre pasan.
- Rutas públicas (/breakers/summary, /api/reconciliation/summary) siempre pasan.
- Desactivable en tests via `PYTEST_CURRENT_TEST` o `DISABLE_INTEGRITY_GUARD`.

---

## CTR-008: OperationTracker

**Módulo:** `app/core/operation_tracker.py`

**Contrato de tracking:**
```python
async def track_operation(operation_data: Dict) -> str  # Retorna operation_id
async def update_operation_status(operation_id: str, status: OperationStatus, result_data: Dict = None)
```

**Ciclo de vida de una operación:**
```
INTENDED -> SUBMITTED -> ACCEPTED -> EXECUTING -> FILLED | PARTIALLY_FILLED | FAILED | CANCELLED | EXPIRED
```

**Invariantes:**
- `operation_id` es determinístico (basado en hash de parámetros).
- Transiciones de estado son monótonas (no se puede volver a un estado anterior).
- Operaciones completadas se mueven a historial.
- Operaciones fallidas se registran separadamente.

---

## Reglas de Compatibilidad

### Para QA Agent:
- Todo contrato tiene tipos explícitos.
- Todo contrato tiene invariantes verificables.
- Los tests pueden verificar contratos sin acceso al exchange (vía stubs).

### Para Maintainer Agent:
- Todo contrato está versionado en este documento.
- Cambios de contrato requieren actualización de este documento.
- Cambios de contrato requieren actualización de tests correspondientes.

### Para Dev Agent:
- Antes de implementar: verificar que el cambio respeta contratos existentes.
- Si se necesita cambio de contrato: proponer actualización aquí primero.
- Nuevos módulos DEBEN definir su contrato aquí antes de implementar.
