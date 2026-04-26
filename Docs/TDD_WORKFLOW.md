# TDD Workflow — GridBot v2.5

Este documento explica cómo escribir, correr y mantener tests en GridBot siguiendo
**Test-Driven Development (RED → GREEN → REFACTOR)** y las reglas duras de
[`TESTING_RULES.md`](../TESTING_RULES.md).

---

## 1. Ciclo TDD adaptado a GridBot

```
┌──────────┐      ┌──────────┐      ┌────────────┐
│   RED    │ ───▶ │  GREEN   │ ───▶ │  REFACTOR  │
│ test     │      │ código   │      │ limpiar    │
│ falla    │      │ pasa     │      │ sin romper │
└──────────┘      └──────────┘      └────────────┘
      ▲                                    │
      └────────────────────────────────────┘
                   (siguiente caso)
```

### 1.1 RED — escribir el test que falla

1. Identificá el comportamiento esperado (idempotencia, validación, breaker, etc.).
2. Escribí el test **antes** de tocar producción.
3. Verificá que falle por la **razón correcta** (assert real, no `ImportError` ni
   fixture rota). Si falla por import, primero arreglá el import.

```bash
pytest tests/test_<modulo>_p1.py::test_<caso> -q -x
```

### 1.2 GREEN — hacer pasar el test

- En GridBot la lógica de negocio **no se cambia** salvo bug confirmado.
- En esta etapa solo se agregan fixtures/mocks o se ajusta un detalle de I/O.
- Al pasar el test, asegurate de que el resto siga verde:

```bash
pytest tests/test_<modulo>_p1.py -q
```

### 1.3 REFACTOR — limpiar sin romper

- Extraer fixtures repetidas a `conftest.py` solo si se usan en ≥ 2 archivos.
- No agregar abstracciones especulativas (over-engineering).
- Volver a correr la suite.

```bash
pytest -q
```

---

## 2. Estructura recomendada de un test

```python
# tests/test_<modulo>_p1.py
"""
Tests de cobertura para app/<ruta>/<modulo>.py
Objetivo: subir cobertura a >= NN % (ver TESTING_RULES.md §3).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_binance_client() -> MagicMock:
    client = MagicMock()
    client.get_account.return_value = {"balances": []}
    return client


def test_caso_feliz(fake_binance_client: MagicMock) -> None:
    # ARRANGE
    ...
    # ACT
    result = ...
    # ASSERT
    assert result == ...
```

**Reglas duras**:

- Todo cálculo monetario **mockeado** debe usar `Decimal`, nunca `float`.
- Para HTTP usar `httpx.AsyncClient` (ver fixtures de `tests/conftest.py`).
- Para servicios externos: `unittest.mock.patch` o doubles. **Nunca** llamadas
  reales a Binance ni a la red.

---

## 3. Variables de entorno (test local)

| Variable | Valor recomendado | Para qué |
|---|---|---|
| `PAPER_TRADING` | `true` | Forzar simulación |
| `BINANCE_TESTNET` | `true` | Si se necesita base URL distinta |
| `FORCE_REAL_MODE` | `false` | Defensa anti-orden real |
| `TRADING_ENABLED` | `false` | Bloqueo global |
| `EMERGENCY_STOP` | `true` | Bloqueo global |
| `INTEGRITY_GUARD_DISABLED` | `1` | Bypass de IntegrityGuard middleware |
| `BINANCE_API_KEY` | `ci_dummy_key` | Cualquier valor no vacío |
| `BINANCE_SECRET_KEY` | `ci_dummy_secret` | Cualquier valor no vacío |
| `DATABASE_URL` | `postgresql://...` | Usar Postgres local o de Docker |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache de tests |
| `EXPORT_OPENAPI` | `0` | Evitar regenerar OpenAPI en imports |

> Tip: copiar `.env.example` a `.env.test` y cargarlo con `set -a && source .env.test && set +a`.

---

## 4. Fixtures comunes (`tests/conftest.py`)

| Fixture / objeto | Tipo | Para qué |
|---|---|---|
| Stub de `binance` SDK | autouse | Reemplaza el módulo real para que no requiera red |
| `BinanceAPIException` (stub) | stub | Permite construir excepciones sin response real |
| `_BROKEN_PREEXISTING_TEST_FILES` | constante | Lista de archivos `*.py` que se *skipean* por drift |
| `pytest_collection_modifyitems` | hook | Aplica el skip a los archivos anteriores |

**Importante**: si un test queda en la lista de drift, no se ejecuta. Para
reactivarlo, primero hay que arreglar la causa raíz y eliminar la entrada
correspondiente de `_BROKEN_PREEXISTING_TEST_FILES`.

---

## 5. Comandos rápidos

```bash
# Suite completa (rápida)
pytest -q

# Con cobertura
pytest -q --cov=app --cov-report=term-missing

# Solo QAA (línea de defensa, debe quedar siempre verde)
pytest tests/test_qaa_*.py -q

# Un módulo específico
pytest tests/test_circuit_breakers_p1.py -q

# Cobertura de un módulo específico
pytest --cov=app.core.auth tests/test_auth_p1.py --cov-report=term-missing

# Rerun solo fallos
pytest --lf -q

# Verboso con captura de prints
pytest -vv -s tests/test_<modulo>_p1.py
```

---

## 6. Flujo "agregar un test nuevo" (checklist)

1. ✅ Identificar el módulo y el comportamiento a cubrir.
2. ✅ Confirmar que cumple un requisito de
   [`TESTING_RULES.md §3`](../TESTING_RULES.md) o §4.
3. ✅ Crear `tests/test_<modulo>_p<N>.py` con docstring que cite el objetivo.
4. ✅ Escribir el test (RED). Correrlo y leer el error.
5. ✅ Si el código ya existe, hacerlo pasar (GREEN). Si falta lógica,
   **frenar**: la lógica de negocio no se toca sin issue + revisión.
6. ✅ Refactor (extraer fixture si aplica).
7. ✅ Verificar cobertura del módulo:
   `pytest --cov=app.<paquete>.<modulo> tests/test_<modulo>_p<N>.py --cov-report=term-missing`.
8. ✅ Correr `pytest tests/test_qaa_*.py -q` (línea de defensa).
9. ✅ Commit con Conventional Commits: `test(<scope>): <descripción>`.

---

## 7. Errores comunes y cómo resolverlos

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ImportError: cannot import name X` | Test apunta a una API que cambió | Actualizar el import o eliminar el test si quedó obsoleto |
| `RuntimeError: There is no current event loop` | Falta `asyncio_mode=auto` | Ya está en `pytest.ini`; revisar fixture custom |
| `BinanceAPIException.__init__() got 'message'` | El stub real exige un `response` | Usar el patrón `_FakeBinanceError` (ver `tests/test_order_validation_p1.py`) |
| `403 Forbidden` en endpoint | Falta `INTEGRITY_GUARD_DISABLED=1` o header `X-API-Key` | Setear env var o headers |
| Cobertura baja un módulo | Tests pasan por *happy path* solamente | Cubrir errores, fallbacks y branches negativos |

---

## 8. Reglas que **no** se relajan

- ❌ No commitear keys reales — usar siempre valores `ci_dummy_*`.
- ❌ No bypassear breakers excepto vía `INTEGRITY_GUARD_DISABLED=1`.
- ❌ No usar `time.sleep()` con valores > 100 ms en tests.
- ❌ No depender de orden de tests (cada uno debe ser idempotente).
- ❌ No tocar lógica de negocio dentro de un PR de tests.
- ✅ Usar `Decimal` para todo lo monetario.
- ✅ Mantener QAA suite en verde.

---

## 9. Skills de Antigravity recomendados

| Skill | Cuándo usarlo |
|---|---|
| `@systematic-debugging` | Debug guiado por evidencia (no parche al ojo) |
| `@phase-gated-debugging` | Bloquea fixes hasta confirmar root cause |
| `@test-driven-development` | Ciclo RED-GREEN-REFACTOR estricto |
| `@tdd-orchestrator` | Coordinar TDD en tareas grandes |
| `@bug-hunter` | Cazar el origen de un test que falla |
| `@verification-before-completion` | Antes de declarar la fase como hecha |
| `@lint-and-validate` | Pre-commit local sobre lo modificado |

Ver el flujo completo en [`AGENTS.md`](../AGENTS.md) sección **Agentes de Calidad y CI/CD**.
