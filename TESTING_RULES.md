# GridBot v2.5 — Reglas de Testing

## Propósito
Define las reglas obligatorias para escribir y mantener tests en el proyecto.
Todo código nuevo o modificado DEBE cumplir con estas reglas.

---

## Reglas Generales

### TR-001: Cobertura Mínima
- Módulos críticos (validadores, sizers, reconciliación, breakers, middleware): **≥ 85%**.
- Módulos de servicio: **≥ 75%**.
- Módulos de API (routes): **≥ 70%**.

### TR-002: Aislamiento de Exchange
- NUNCA llamar al exchange real en tests (salvo flag explícito `USE_REAL_BINANCE=1`).
- Usar stubs/fixtures del `conftest.py` para simular respuestas de Binance.
- Toda nueva interacción con Binance debe tener su stub correspondiente.

### TR-003: Decimal en Tests Financieros
- Todo test que involucre precios, cantidades, balances o PnL DEBE usar `Decimal`.
- Los assertions de igualdad monetaria DEBEN usar `Decimal` con precisión explícita.
- Ejemplo:
```python
from decimal import Decimal
assert result.quantity == Decimal("0.001")
assert result.notional >= Decimal("10.0")
```

### TR-004: Tests Determinísticos
- Todo test DEBE ser determinístico (mismo resultado en cada ejecución).
- No depender de hora actual, random, o estado externo.
- Usar `freezegun` o mocks de datetime si se necesita tiempo fijo.

### TR-005: Nomenclatura
- Archivos: `test_<modulo>.py`
- Funciones: `test_<que_prueba>_<condicion>_<resultado_esperado>`
- Ejemplo: `test_validate_order_quantity_below_min_rejects`

---

## Categorías de Tests Obligatorios

### Categoría 1: Tests de Invariantes (Prefijo: `test_inv_`)
Verifican que las invariantes de INVARIANTS.md se cumplen.

```python
def test_inv_001_no_float_in_order_validation():
    """INV-001: OrderValidator nunca retorna float en campos monetarios."""

def test_inv_002_order_rejected_when_filters_fail():
    """INV-002: Orden rechazada si no pasa filtros del exchange."""

def test_inv_003_order_blocked_when_breaker_active():
    """INV-003: Orden bloqueada si hay breaker activo."""

def test_inv_004_client_order_id_deterministic():
    """INV-004: clientOrderId es determinístico para mismos parámetros."""
```

### Categoría 2: Tests de Contratos (Prefijo: `test_ctr_`)
Verifican que los contratos de CONTRACTS.md se respetan.

```python
def test_ctr_001_validate_order_returns_expected_schema():
    """CTR-001: validate_order_parameters retorna schema esperado."""

def test_ctr_002_execute_order_checks_breakers_first():
    """CTR-002: execute_order consulta breakers antes de enviar."""

def test_ctr_003_reconciliation_detects_discrepancy():
    """CTR-003: ReconciliationService detecta discrepancias."""
```

### Categoría 3: Tests de Regresión (Prefijo: `test_reg_`)
Verifican que bugs corregidos no reaparecen.

```python
def test_reg_float_in_notional_calculation():
    """Regresión: notional se calcula con Decimal, no float."""

def test_reg_order_without_validation():
    """Regresión: orden no se envía sin validación previa."""
```

### Categoría 4: Tests de Integración (Prefijo: `test_int_`)
Verifican la interacción entre módulos.

```python
async def test_int_full_order_flow():
    """Integración: flujo completo de validación -> ejecución -> reconciliación."""

async def test_int_breaker_blocks_middleware():
    """Integración: breaker activo bloquea requests via middleware."""
```

---

## Reglas para Tests de Módulos Críticos

### OrderValidator
- Test con cada filtro: PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL.
- Test con valores exactamente en el límite (boundary testing).
- Test con stepSize/tickSize que producen redondeo.
- Test que notional se valida DESPUÉS del redondeo.

### TradeExecutor
- Test que consulta breakers antes de ejecutar.
- Test que valida filtros antes de enviar.
- Test que genera clientOrderId determinístico.
- Test que maneja respuesta FILLED, PARTIALLY_FILLED, y error.
- Test que actualiza balances correctamente tras ejecución.

### ReconciliationService
- Test que detecta discrepancia real.
- Test que activa breaker cuando discrepancia > umbral.
- Test que no activa breaker si discrepancia < umbral.
- Test que registra latencia.

### CircuitBreakers
- Test que is_trading_halted() refleja estado correcto.
- Test de cooldown (no flapping).
- Test de modo crítico activa todos los breakers.
- Test de desactivación reseta estado.

### RiskManager
- Test de Kelly fraccional con valores conocidos.
- Test de fallback a ATR cuando Kelly no aplica.
- Test de límites de posición (cap_symbol_pct, cap_equity_pct).
- Test de multiplicador de régimen.

---

## Fixtures Obligatorias (conftest.py)

Todo test que interactúe con Binance debe usar:
- `mock_binance_client_autouse`: stub automático del cliente Binance.
- `mock_config`: configuración mínima para grid manager.

Para tests de API:
- `client`: TestClient de FastAPI.

---

## Ejecución

```bash
# Suite completa
pytest -q

# Con cobertura
pytest --cov=app --cov-report=term-missing

# Solo tests de invariantes
pytest -k "test_inv_" -q

# Solo tests de contratos
pytest -k "test_ctr_" -q

# Solo tests de integridad del sistema
pytest tests/test_system_integrity.py -q
```

---

## Reglas de CI

1. Todo PR debe pasar `pytest -q` sin fallos.
2. Cobertura no debe disminuir respecto a main.
3. Tests de invariantes nunca se pueden skipear.
4. Tests de contratos nunca se pueden skipear.
5. Tests que requieren exchange real se marcan con `@pytest.mark.real_exchange`.
