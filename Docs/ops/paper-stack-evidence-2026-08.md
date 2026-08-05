# Evidencia — Paper stack + auditoría de defaults (2026-08-05)

Track G del hito **paper stack estable al 2026-08-20**.
Branch: `chore/s0-paper-deploy-checklist` (stacked sobre `feat/s1-mode-clarity`, PR #33).

Checklist origen: `Docs/engineering/deploy-checklist-paper.md` del monorepo.
Protocolo de registro: `Docs/engineering/validation-protocol.md` del monorepo.

Entorno: macOS 24.6.0, Python 3.11.13, Docker CLI 29.4.0, Compose v5.1.1.
Todo se ejecutó en **paper**, con credenciales placeholder de `env.example`.
No se activó `FORCE_REAL_MODE` ni se usó ninguna key real.

---

## 1. Veredicto: ¿los defaults arman live?

**No. Sin variables de entorno el stack no queda armado para operar real.** Pero tampoco
quedaba en paper: caía en un estado intermedio (`real_blocked`) cuya única protección efectiva
era la ausencia de credenciales válidas de Binance. Eso es lo que este PR corrige.

Evidencia directa, sin ninguna variable definida:

```bash
env -i python3.11 -c "import sys; sys.path.insert(0,'.'); \
  from app.core.trading_mode import get_trading_mode_snapshot; print(get_trading_mode_snapshot())"
```

```
{'paper_trading': False, 'force_real_mode': False, 'trading_enabled': True,
 'emergency_stop': False, 'binance_testnet': False, 'effective_mode': 'real_blocked'}
```

`compute_effective_mode` devuelve `real_armed` solo si `force_real_mode=True`, y su default es
`false` en todas las capas revisadas. Por eso el "no arma live" es firme.

### Defaults efectivos por capa (antes de este PR)

| Capa | `PAPER_TRADING` | `FORCE_REAL_MODE` | `TRADING_ENABLED` |
|------|-----------------|-------------------|-------------------|
| `app/core/trading_mode.py` | `false` | `false` | `true` |
| `app/core/config.py` | `false` | n/a | n/a |
| `scripts/validate_startup.py` | `true` | `false` | `false` |
| `env.example` | `false` (explícito) | ausente | `true` |
| `docker-compose.local.yml` | `true` (explícito, gana sobre `.env`) | `""` | `true` |
| `docker-compose.yml` | `${PAPER_TRADING:-false}` | `${FORCE_REAL_MODE:-}` | `${TRADING_ENABLED}` (vacío ⇒ falsy) |

Las capas discrepaban: el gate de arranque asumía paper, la plantilla que el operador copia a
`.env` asumía real. Ese es el hallazgo principal y es lo que se corrigió.

### Hallazgos de riesgo (no todos corregidos acá)

1. **`FORCE_REAL_MODE` no es necesario para mandar una orden real.** El path de ejecución
   (`app/core/optimized_grid_manager._place_order` línea 744, `app/services/binance_service.py`
   línea 94) bifurca solo por `PAPER_TRADING`. Con `PAPER_TRADING=false` + credenciales válidas
   se manda orden real sin confirmación adicional, mientras la API sigue reportando
   `real_blocked`: **divergencia entre lo que la API dice y lo que el runtime hace.**
   Owner sugerido: Track D (live gate / `trading_mode.py`) + Track F.
2. **`TRADING_ENABLED` y `EMERGENCY_STOP` son cosméticos como variables de entorno.** Solo se
   leen en `trading_mode.py` para el snapshot. `RiskManager` arranca con `trading_enabled=True`
   / `emergency_stop=False` en memoria y no consulta el entorno: poner `TRADING_ENABLED=false`
   en `.env` **no** apaga el trading. Owner sugerido: Track F.
3. **Prefijo de API key en logs.** `app/core/optimized_grid_manager.py:156,191`,
   `app/services/binance_client_singleton.py:136,160` y
   `app/services/binance_credentials.py:104,134,147,255` loguean `api_key[:10]`. Capturado en
   los logs del worker paper: `✅ Cliente de Binance verificado - API Key: YOUR_BINAN...`.
   Con keys reales, eso son 10 caracteres de secreto en Papertrail/stdout.
   Owner sugerido: `trading-security`.
4. **En paper hay tráfico autenticado saliente a Binance.** `CommissionManager.__init__`
   (`app/services/commission_manager.py:34-45`) crea el cliente y llama `get_account()` si hay
   credenciales, sin mirar `PAPER_TRADING`. Capturado con placeholders:
   `No se pudieron actualizar comisiones: APIError(code=-2014): API-key format invalid`.
   Es read-only, pero rompe la premisa de "paper no habla con el exchange".
5. **`beat` dispara `trading-cycle-tick` cada 60 s** en cuanto el stack sube
   (`app/core/celery_app.py:86`). El flag de paper no es decorativo: es lo único que separa ese
   ciclo automático de una orden real.

---

## 2. Cambios paper-safe aplicados en este PR

Todos endurecen en dirección **más paper** o arreglan observabilidad; ninguno habilita nada nuevo.

| Cambio | Por qué |
|--------|---------|
| `env.example`: `PAPER_TRADING=true`, `FORCE_REAL_MODE=` y `EMERGENCY_STOP=false` documentados | Copiar la plantilla a `.env` dejaba el stack apuntando a real |
| `docker-compose.yml`: `${PAPER_TRADING:-true}` en `api`, `celery_worker`, `celery_beat` | Sin la variable definida el stack arrancaba en modo real |
| `docker/prometheus/prometheus.yml`: bloque `alerting:` hacia `alertmanager:9093` | Las 45 reglas (breakers, error rate de órdenes, desync de reconciliación) evaluaban sin notificar a nadie |
| `docker-compose.local.yml`: servicio `alertmanager` + volumen | El stack local no tenía receptor de alertas |
| `docker-compose*.yml`: `TRUSTED_HOSTS` incluye `api` | Prometheus scrapeaba `http://api:8000/metrics` y recibía **400** del `TrustedHostMiddleware`: el target `gridbot-api` estaba **down**, o sea el stack no tenía métricas de aplicación |
| `docker-compose.local.yml`: `container_name` y puertos parametrizados (`GRIDBOT_PREFIX`, `API_PORT`, …) con los defaults actuales | Sin esto es imposible levantar el stack paper si ya hay otro GridBot corriendo: nombres y puertos chocan |
| `scripts/validate_startup.py`: credenciales Binance son advertencia en paper | Con placeholders el gate bloqueaba el arranque paper desde un clon limpio |
| `scripts/validate_startup.py`: `FORCE_REAL_MODE=true` + `PAPER_TRADING=true` ahora falla | Config contradictoria que en runtime termina en real: fail closed |
| `scripts/smoke_paper_mode.py` (nuevo) + `make smoke-paper` / `smoke-paper-asgi` | El checklist pedía verificar `effective_mode`; ahora es un gate ejecutable que falla si no es `paper`. El modo `--asgi` corre sin Docker |
| `make up` corre `smoke-paper` al final | Levantar el stack sin verificar el modo era el agujero operativo del checklist |
| `make config-check` / `make paper-flags` | Validación estática del compose cuando no hay daemon Docker |
| `tests/test_config_guards.py` | Los dos tests existentes estaban **rojos** (el `ValueError` escapaba en `importlib.reload`, fuera del `try`); se arreglaron y se agregaron 7 guardas de defaults |

`docker-compose.local.yml` ya forzaba `PAPER_TRADING: "true"` en `environment`, que **gana sobre
`env_file: .env`**. Se verificó y quedó fijado por test.

---

## 3. Evidencia ejecutada

### 3.1 Tests (Python 3.11)

```bash
python3.11 -m pytest tests/test_config_guards.py tests/test_trading_mode.py -q
```

```
18 passed, 2 warnings
```

Antes del PR: `2 failed, 8 passed` (los dos guards de producción estaban rotos).

### 3.2 Stack paper completo en Docker

El stack se levantó en un proyecto aislado, con prefijo y puertos alternativos, para no tocar el
stack `grid_bot` preexistente del operador:

```bash
cp env.example .env
GRIDBOT_PREFIX=gridbot_paper API_PORT=8010 DB_PORT=5442 REDIS_PORT=6389 \
FLOWER_PORT=5565 PROMETHEUS_PORT=9190 ALERTMANAGER_PORT=9193 \
docker compose -f docker-compose.local.yml -p gridbot_paper_s0 up -d \
  db redis migrate api worker beat flower prometheus alertmanager
```

```
NAME                         STATUS
gridbot_paper_alertmanager   Up (healthy)
gridbot_paper_api            Up (healthy)
gridbot_paper_beat           Up (healthy)
gridbot_paper_db             Up (healthy)
gridbot_paper_flower         Up (healthy)
gridbot_paper_prometheus     Up (healthy)
gridbot_paper_redis          Up (healthy)
gridbot_paper_worker         Up (healthy)
```

`migrate` corrió `ensure_pg_grants.py` + `alembic upgrade head` y salió 0.

### 3.3 Smoke paper contra el stack levantado

```bash
curl -s http://localhost:8010/health
curl -s http://localhost:8010/health/trading-mode
API_PORT=8010 make smoke-paper
```

```
{"status":"healthy","timestamp":"2026-08-05T14:34:21","trading":{"paper_trading":true,
 "force_real_mode":false,"trading_enabled":true,"emergency_stop":false,
 "binance_testnet":false,"effective_mode":"paper"}}

--- Smoke paper mode (http://localhost:8010) ---
[PASS] /health → effective_mode=paper
[PASS] /health/trading-mode → effective_mode=paper
[PASS] /metrics → HTTP 200 (17291 bytes)
[PASS] Stack en modo PAPER: effective_mode=paper y /metrics up
```

`/health/trading-mode` devuelve el mismo snapshot que `/health`.

### 3.4 Observabilidad

Antes del fix de `TRUSTED_HOSTS`:

```
gridbot-api | down | server returned HTTP status 400 Bad Request
```

Después de recrear `api` con `TRUSTED_HOSTS=...,api`:

```
gridbot-api    | up |
gridbot-celery | up |
prometheus     | up |
```

Alertmanager efectivamente conectado (antes del bloque `alerting:` la lista venía vacía):

```bash
curl -s http://localhost:9190/api/v1/alertmanagers
{"status":"success","data":{"activeAlertmanagers":[{"url":"http://alertmanager:9093/api/v2/alerts"}],
 "droppedAlertmanagers":[]}}
```

Reglas cargadas: **8 grupos / 45 reglas** (`TradingOrderErrors`, `LowBalance`,
`SignificantLosses`, `RedisDown`, `PostgreSQLDown`, `CeleryWorkerDown`, …).
Los targets `redis`, `postgres` y `cadvisor` quedaron down porque esos exporters no se
levantaron en esta corrida (no forman parte del checklist paper).

### 3.5 Ciclo paper observado en el worker

```bash
docker logs gridbot_paper_worker --tail 25
```

```
app.core.paper_trading   | ✅ Estado de paper trading cargado: $1000.00
app.core.circuit_breakers| 🔧 Módulo de circuit breakers inicializado
app.core.risk_manager    | Position size for GENERIC: 60.0000 USDT (ATR method)
app.services.strategy_selector | ERROR | Error selecting strategy for ETHUSDT:
                           unsupported operand type(s) for /: 'float' and 'decimal.Decimal'
app.services.trading_tasks | [Cycle] Decisión parcial registrada (fase evaluación)
celery.app.trace | Task trading_cycle_tick succeeded in 5.12s: {'status': 'ok'}
```

Cero órdenes reales (`grep -ciE "orden real|place_order real"` → `0`). Pero el ciclo trae dos
cosas que importan para el hito:

- **Bug de integridad financiera:** `strategy_selector` mezcla `float` con `Decimal` y **toda
  selección de estrategia falla** (`app/services/strategy_selector.py:411`). El ciclo termina en
  "decisión parcial": el stack está estable pero no está decidiendo nada. Owner sugerido:
  Track A / quant.
- **Prefijo de API key en logs** (hallazgo §1.3).

### 3.6 Validación pre-startup en paper (clon limpio + `env.example`)

```bash
cp env.example .env && make validate
```

```
Resumen:
  [PASS] Pasadas: 17
  [FAIL] Fallos: 0
  [WARN] Advertencias: 1
    * BINANCE_API_KEY demasiado corto (got 25)
[PASS] Pre-startup checks PASSED!
```

### 3.7 Casos negativos del gate (deben bloquear)

```bash
PAPER_TRADING=false python3 scripts/validate_startup.py
```

```
[FAIL] CRÍTICO: PAPER_TRADING=false pero FORCE_REAL_MODE no es true.
[FAIL] STARTUP BLOCKED: Errores criticos encontrados
```

```bash
PAPER_TRADING=true FORCE_REAL_MODE=true python3 scripts/validate_startup.py
```

```
[FAIL] CRÍTICO: FORCE_REAL_MODE=true junto a PAPER_TRADING=true. FORCE_REAL_MODE anula paper.
[FAIL] STARTUP BLOCKED: Errores criticos encontrados
```

### 3.8 Compose resuelto

```bash
docker compose -f docker-compose.local.yml config -q   # válido, incluido alertmanager
make paper-flags
```

Los cinco servicios de app (`api`, `worker`, `beat`, `migrate`, `flower`) resuelven:

```
PAPER_TRADING: "true"   FORCE_REAL_MODE: ""   TRADING_ENABLED: "true"
EMERGENCY_STOP: "false" BINANCE_TESTNET: "false"
```

Antes del PR, `flower` heredaba `PAPER_TRADING: "false"` de `.env` (no tradea, pero mostraba
cómo la plantilla insegura se filtraba a cualquier servicio sin override).

Default de producción sin variables en el entorno:

```bash
docker compose --env-file /dev/null -f docker-compose.yml config | grep PAPER_TRADING
PAPER_TRADING: "true"
```

### 3.9 Smoke sin Docker (fallback documentado)

```bash
python3.11 scripts/smoke_paper_mode.py --asgi
```

```
[PASS] /health → effective_mode=paper
[PASS] /health/trading-mode → effective_mode=paper
[PASS] /metrics → HTTP 200 (15290 bytes)
```

Sirve cuando el daemon de Docker no está disponible, que fue la situación al inicio de esta
sesión.

Nota de routing verificada de paso: `app/main.py` define un `/health` mínimo en la línea 642,
pero `system_routes` se registra antes (línea 379), así que el `/health` que responde es el que
incluye el snapshot de trading. La ruta de `main.py` quedó sombreada (deuda cosmética, Track D).

---

## 4. Checklist paper — estado trazable

Trazabilidad contra `Docs/engineering/deploy-checklist-paper.md` del monorepo.

### Pre

- [x] Sin API keys reales en `.env` de trabajo (placeholders de `env.example`; `.env` está en `.gitignore` y no se commitea)
- [x] `PAPER_TRADING=true` (ahora default de la plantilla; test lo fija)
- [x] `FORCE_REAL_MODE` unset/false (vacío en `env.example` y en ambos compose; test lo fija)
- [x] Revisar `docker-compose.local.yml` (paper forzado: `environment` gana sobre `env_file`)

### Steps

- [x] `docker compose -f docker-compose.local.yml up -d` — 8 servicios healthy (§3.2)
- [x] `GET /health` → `effective_mode` = `paper` (§3.3)
- [x] `GET /health/trading-mode` → mismo snapshot (§3.3)
- [x] `/metrics` up — 200 y ahora **scrapeado** por Prometheus (§3.4)
- [x] Smoke: sin órdenes reales — `BinanceService` en simulación, `_place_order` en rama paper,
      cero órdenes reales en logs. Caveat: `CommissionManager` hace un `get_account()`
      autenticado si hay keys (§1.4)

### Post

- [ ] **FALLA** Logs sin secrets — se loguea `api_key[:10]` en varios módulos (§1.3)
- [x] Breakers en estado conocido — `circuit_breakers` inicializa en el worker; 45 reglas
      cargadas y ruta a Alertmanager verificada. Sin disparo de alerta sintética end-to-end
- [x] Registrar resultado en validation-protocol → este documento (linkearlo desde
      `Docs/engineering/validation-protocol.md` queda para el owner del monorepo)

**Veredicto de protocolo:** `ITERATE`. El stack paper levanta, reporta `paper` de forma
inequívoca y ya tiene métricas y alertas ruteadas. Falta cerrar dos cosas antes de declarar el
hito: el secreto parcial en logs y el bug `float`/`Decimal` que deja al ciclo sin decidir.
No aplica `PROMOTE_LIVE` (prohibido sin gate humano explícito).

---

## 5. Bloqueos encontrados y cómo se resolvieron

1. **Docker daemon caído al inicio.** `docker info` fallaba con
   `failed to connect to the docker API at unix:///…/docker.sock`. Se levantó Docker Desktop y
   quedó operativo (29.4.0). Para escenarios sin daemon queda `make smoke-paper-asgi`.
2. **Colisión con el stack `grid_bot` preexistente del operador.** Hay contenedores del proyecto
   `~/Documents/grid_bot`: `gridbot_db`, `gridbot_redis`, `gridbot_flower` corriendo (5432,
   6379, 5555) y `gridbot_api`, `gridbot_prometheus`, `gridbot_grafana`, `gridbot_alertmanager`
   en `Exited`. Como `container_name` era fijo, `up` fallaba por nombre tomado incluso contra
   contenedores detenidos. **No se detuvo ni borró nada del operador**: se parametrizaron
   nombres y puertos (§2) y el stack paper se levantó en paralelo. Al terminar se hizo
   `down -v` solo del proyecto `gridbot_paper_s0` y se borraron sus imágenes; los contenedores
   del operador quedaron en el mismo estado que al inicio.
3. **Build de imagen muy pesado.** `requirements-ml.txt` instala TensorFlow (589 MB de wheel)
   y vectorbt aunque `ML_ENABLED=false`: el build tomó ~14 min en frío. No bloquea, pero es
   fricción real para reproducir el paper stack y para CI.
4. **Grafana y los exporters no se levantaron** en esta corrida (no son parte de los steps del
   checklist paper y acortaban el ciclo de verificación). Quedan sin evidencia.

---

## 6. Riesgos para el hito del 2026-08-20

| Riesgo | Impacto | Mitigación propuesta |
|--------|---------|---------------------|
| `strategy_selector` falla por `float` / `Decimal` y el ciclo paper no decide (§3.5) | **Alto**: el stack "estable" no produce señales; sin esto no hay tear-sheet paper | Track A / quant: normalizar a `Decimal` y test de regresión |
| `api_key[:10]` en logs (§1.3) | **Alto**: fuga parcial de secreto a stdout/Papertrail | `trading-security`: enmascarar por completo |
| `FORCE_REAL_MODE` no es requisito para operar real (§1.1) | **Alto**: un `.env` con `PAPER_TRADING=false` manda órdenes reales mientras la API dice `real_blocked` | Track D: exigir `force_real_mode` en el path de órdenes, no solo en el snapshot |
| `TRADING_ENABLED` / `EMERGENCY_STOP` no cortan nada por entorno (§1.2) | **Alto**: el kill-switch documentado no funciona como se cree | Track F: leer entorno en `RiskManager` y cortar el ciclo |
| Ciclo paper solo observado unos minutos | Medio: no hay datos de estabilidad sostenida ni de latencia | Correr 24–48 h de paper con Prometheus/Grafana y sacar tear-sheet |
| Alertas nunca disparadas end-to-end | Medio: la ruta a Alertmanager está probada, el receptor no | Disparar una alerta sintética con el stack arriba |
| Tráfico autenticado a Binance en paper (§1.4) | Medio: rompe aislamiento y consume rate limit | Gatear `CommissionManager` por modo paper |
| Build de imagen ~14 min / TensorFlow innecesario en paper (§5.3) | Medio: encarece cada iteración y el CI | Mover `requirements-ml.txt` a un stage/imagen opcional detrás de `ML_ENABLED` |

---

## 7. Cómo reproducir

```bash
cp env.example .env                  # queda en paper por default
make validate                        # gate pre-startup (paper: keys son warning)
make config-check                    # compose resuelto, sin levantar nada
make paper-flags                     # flags de trading efectivas
make smoke-paper-asgi                # smoke sin Docker: exige effective_mode=paper
python3.11 -m pytest tests/test_config_guards.py tests/test_trading_mode.py -q

# stack completo (usa los defaults 8000/5432/6379/… si están libres)
make up                              # validate + up + health + smoke-paper
make smoke-paper                     # gate contra http://localhost:$(API_PORT)

# stack paper en paralelo a otro GridBot ya corriendo
GRIDBOT_PREFIX=gridbot_paper API_PORT=8010 DB_PORT=5442 REDIS_PORT=6389 \
FLOWER_PORT=5565 PROMETHEUS_PORT=9190 ALERTMANAGER_PORT=9193 \
docker compose -f docker-compose.local.yml -p gridbot_paper up -d
API_PORT=8010 make smoke-paper
```

URLs locales del stack paper (defaults): API `http://localhost:8000`, métricas `:8000/metrics`,
Flower `:5555` (admin/admin), Prometheus `:9090`, Alertmanager `:9093`,
Grafana `:3000` (admin/gridbot123).

**Pasar a live sigue prohibido sin gate humano explícito** (`40-no-live-without-gate`). Nada de
este documento habilita esa transición.
