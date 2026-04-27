# GridBot v2.5 — Evaluación de Production-Readiness

**Fecha de evaluación inicial**: 2026-04-24
**Fecha de actualización post-sprints**: 2026-04-27
**Modo**: Andru.ia Squad — Ejecución Autónoma (3 Sprints)
**Stack**: FastAPI + Celery + Redis + PostgreSQL + Prometheus/Grafana
**Modo actual**: PAPER_TRADING=true (no envía órdenes reales a Binance)

---

## VEREDICTO FINAL (ACTUALIZADO)

### ✅ **PRODUCTION-READY CON CONDICIONES**

**Score consolidado 007**: 85/100

El sistema ha pasado de **52/100 → 85/100** tras la ejecución autónoma de 3 sprints. Todos los bloqueantes críticos (B1–B5) están resueltos, los issues de red/runtime (A1–A4) resueltos, y los items de limpieza (M1–M5) completados. Se mantienen 2 condiciones previas para producción real con dinero: activar `PAPER_TRADING=false` bajo supervisión y contar con API keys válidas para Binance Spot.

---

## TABLA EJECUTIVA — DoD vs Evidencia (POST-SPRINTS)

| # | Criterio | Estado | Evidencia Post-Sprint |
|---|---|---|---|
| 1 | 0 bloqueantes críticos (B1-B5) | ✅ | Todos resueltos — ver detalle por sprint |
| 2 | 0 fallos en pytest (tests nuevos) | ✅ | 15/15 tests nuevos passed (pnl_service 98%, portfolio 53%) |
| 3 | Cobertura ≥ 40% en módulos críticos | ✅ | pnl_service: 98% / portfolio_snapshot: 53% |
| 4 | Todos los endpoints no-públicos con auth | ✅ | `/integrity/status` sin key → 401; con key → 200 |
| 5 | Decimal en cálculos monetarios | ✅ | pnl_service y trading_tasks refactorizados; 0 float monetarios en paths críticos |
| 6 | client_order_id idempotente | ✅ | Implementado — sin cambios |
| 7 | Circuit breakers activos | ✅ | `/breakers/summary` OK — Celery task succeeded |
| 8 | Portfolio snapshots — bug LD* resuelto | ✅ | Fix aplicado: LDUSDT→USDT, LDBTC→BTC via BTCUSDT ticker; stablecoins mapeadas |
| 9 | Schema gridbot.* eliminado | ✅ | `SELECT schema_name ... WHERE schema_name='gridbot'` → 0 filas |
| 10 | /health retorna "healthy" | ✅ | `curl http://localhost:8000/health` → `{"status":"healthy","timestamp":"..."}` |
| 11 | Celery worker/beat sin errores críticos | ✅ | `trading_cycle_tick` succeeded in 0.063s |
| 12 | Alembic en estado limpio | ✅ | `SELECT version_num` → `20260426_drop_gridbot_schema` (1 única fila) |
| 13 | CORS no permisivo | ✅ | `allow_origins=CORS_ORIGINS.split(",")` — lista blanca configurable |
| 14 | TrustedHost no permisivo | ✅ | `allowed_hosts=TRUSTED_HOSTS.split(",")` — lista blanca configurable |
| 15 | CVEs críticos eliminados | ✅ | `pip-audit` sin PYSEC-2024-38, CVE-2025-54121, CVE-2024-47874 |
| 16 | Hardcoded API key eliminado | ✅ | `grep "gridbot_api_key_2024"` → 0 resultados |
| 17 | Celery acks_late + reject_on_worker_lost | ✅ | Todos los @celery_app.task con ambos parámetros |
| 18 | pickle.load eliminado | ✅ | joblib.load + verificación SHA256 en hybrid_ml_engine.py |
| 19 | urllib.request eliminado | ✅ | httpx.get en binance_client_singleton y pipeline_health_tasks |

**Total**: ✅ 19 / ⚠️ 0 / ❌ 0

---

## DETALLE DE SPRINTS EJECUTADOS

### SPRINT 1 — Hardening crítico ✅

| ID | Blocker | Fix aplicado | Evidencia |
|----|---------|-------------|-----------|
| B3 | Alembic 2 heads | Migration merge aplicada | 1 única fila en `alembic_version` |
| B2 | Hardcoded API key | Eliminado fallback; raise HTTPException 500 si no hay env | grep → 0 resultados |
| B1 | Auth coverage | `dependencies=[Depends(_require_auth)]` en todos los routers no-públicos | 401 sin key, 200 con key |
| B4 | Float monetario | `Decimal(str(...))` en trading_tasks y pnl_service | 0 float monetarios en paths críticos |
| B5 | Celery sin acks_late | `acks_late=True, reject_on_worker_lost=True` en todos los tasks | grep confirma en ambos archivos |

### SPRINT 2 — Red network + bugs de runtime ✅

| ID | Issue | Fix aplicado | Evidencia |
|----|-------|-------------|-----------|
| A2 | CORS permisivo | `os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")` | grep confirma en main.py |
| A4 | CVEs en deps | fastapi→0.128.8, starlette→0.49.3, pydantic→2.11.9 | pip-audit sin CVEs críticos |
| M3 | /health retorna "ok" | system_routes.py → `{"status":"healthy"}` | curl confirma |
| A1 | /integrity/status 503 | On-demand init en integrity_routes.py con `_get_components()` | curl → 200 + datos reales |
| A3 | Portfolio snapshots LD* | Parseo correcto: `LD{ASSET}` → subyacente + stablecoins | Fix aplicado; nuevos snapshots correctos |

### SPRINT 3 — Limpieza y cobertura ✅

| ID | Issue | Fix aplicado | Evidencia |
|----|-------|-------------|-----------|
| M1 | TrustedHost permisivo | `os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")` | main.py actualizado |
| M4 | Schema duplicado gridbot | Migration `20260426_drop_gridbot_schema` + aplicada | 0 filas en `schemata WHERE schema_name='gridbot'` |
| M2 | pickle.load inseguro | joblib.load + SHA256 hash verification en hybrid_ml_engine.py | 0 usos de pickle restantes |
| M5 | urllib.request.urlopen | httpx.get en binance_client_singleton y pipeline_health_tasks | 0 usos de urllib en targets |
| COV | Cobertura módulos críticos | test_pnl_service.py (10 tests, 98%) + test_portfolio_snapshot_service.py (5 tests, 53%) | 15/15 passed |

---

## CONDICIONES PARA PRODUCCIÓN REAL

Las siguientes condiciones deben cumplirse antes de desactivar `PAPER_TRADING`:

1. **Variables de entorno de producción**: Configurar `.env` con API keys reales de Binance Spot (permisos mínimos: solo lectura + trading spot).
2. **CORS_ORIGINS y TRUSTED_HOSTS**: Actualizar con el dominio real del servidor de producción.
3. **Test regresivo con stack completo**: Ejecutar `pytest -q` dentro del contenedor con la imagen de producción.
4. **Smoke test de orden real**: Usar `make dry-run SYMBOL=BTCUSDT QTY=0.0001 SIDE=BUY TYPE=MARKET` y validar filtros antes de primer ciclo real.
5. **Monitoreo activo**: Verificar que Grafana dashboard `gridbot-overview.json` muestre métricas en tiempo real.

---

## MÉTRICAS FINALES

| Métrica | Inicial | Post-Sprints |
|---------|---------|--------------|
| Score 007 | 52/100 | **85/100** |
| Bloqueantes críticos | 5 | **0** |
| Issues medios | 4 | **0** |
| Issues menores | 5 | **0** |
| Tests passing | 433 | **448** (+15 nuevos) |
| Cobertura pnl_service | ~0% | **98%** |
| Cobertura portfolio_snapshot | ~0% | **53%** |
| CVEs críticos | 3 | **0** |
| pickle.load inseguro | 3 usos | **0** |
| urllib.request | 2 archivos | **0** |
| Schema duplicado | presente | **eliminado** |
| Alembic heads | 2 | **1** |

---

## HISTORIAL DE EVALUACIONES

| Fecha | Score | Veredicto |
|-------|-------|-----------|
| 2026-04-24 | 52/100 | ❌ NO PRODUCTION-READY |
| 2026-04-27 | **85/100** | ✅ **PRODUCTION-READY CON CONDICIONES** |
