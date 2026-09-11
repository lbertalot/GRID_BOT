# CI/CD Runbook — GridBot v2.5

Pipeline de referencia para `.github/workflows/ci.yml`. Este documento describe
cada job, cuándo falla, cómo se debuggea localmente y cómo se evoluciona el gate
de cobertura.

---

## 1. Diagrama del pipeline

```
                          push / pull_request
                                 │
                                 ▼
        ┌────────────────┬────────────────────┐
        │   1. lint      │  2. security-scan  │   (paralelos)
        │ pyflakes (★)   │  bandit (★)        │
        │ ruff           │  pip-audit (★)     │
        └───────┬────────┴──────────┬─────────┘
                │                   │
                ▼                   ▼
            ┌────────────────────────┐
            │    3. test (★)         │
            │  Postgres + Redis      │
            │  pytest --cov --gate   │
            │  + QAA suite (★)       │
            │  + Codecov upload      │
            └──────────┬─────────────┘
                       │
                       ▼
            ┌────────────────────────┐
            │  4. migrations (★)     │
            │  alembic upgrade head  │
            └──────────┬─────────────┘
                       │
                       ▼ (solo en main / push)
            ┌────────────────────────┐
            │  5. docker             │
            │  build & push GHCR     │
            └──────────┬─────────────┘
                       │
                       ▼ (solo main)
            ┌────────────────────────┐
            │  6. deploy → Heroku    │
            │  + alembic upgrade     │
            └────────────────────────┘

(★) = bloqueante. El resto sólo se ejecuta si los previos pasaron.
```

---

## 2. Detalle por job

### 2.1 `lint`

- **Bloqueante en**: errores reales detectados por `pyflakes` (`undefined name`,
  `invalid syntax`, `may be undefined`).
- **No bloqueante en**: warnings de `ruff check` (se adopta gradualmente). Para
  forzar el bloqueo, eliminar `|| true` del step de ruff.
- **Cómo reproducir local**:
  ```bash
  pip install pyflakes ruff
  python -m pyflakes app | tee pyflakes.log
  ruff check app tests
  ```

### 2.2 `security-scan` (BLOQUEANTE)

- **Bandit**: vulnerabilidades estáticas en `app/` con severidad MEDIA/ALTA y
  confianza ≥ MEDIA. Skip explícito de `B101` (assert en tests) y `B601`
  (paramiko, no usado).
- **pip-audit**: CVEs en `requirements.txt`. Lista de CVEs ignorados con
  justificación documentada en el propio workflow (campo `--ignore-vuln`).
- **Cómo reproducir local**:
  ```bash
  pip install bandit pip-audit
  bandit -r app --skip B101,B601 --severity-level medium --confidence-level medium -f txt
  pip-audit -r requirements.txt
  ```
- **Falla típica**: nuevo CVE en un paquete. Procedimiento:
  1. Verificar si hay versión parcheada → bumpear `requirements.txt`.
  2. Si no hay parche y el riesgo es aceptable, agregar `--ignore-vuln <ID>` con
     comentario que justifique (vector, exposición, plan).
  3. Documentar en este runbook.

### 2.3 `test` (BLOQUEANTE)

- **Servicios**: Postgres 15 + Redis 7 como containers de servicios de GitHub Actions.
- **Comando principal**:
  ```bash
  pytest tests/ -q --maxfail=10 --disable-warnings \
    --cov=app --cov-report=xml:coverage.xml \
    --cov-report=term-missing:skip-covered \
    --cov-fail-under=${COVERAGE_FAIL_UNDER}
  ```
- **Gate escalonado**: la variable `COVERAGE_FAIL_UNDER` (env del workflow)
  arranca históricamente en baseline ~25–29 %. **Actual (post-COV-5.9, 2026-08-10): `80`**.

  | Fecha (objetivo)  | Gate | Justificación                              |
  |-------------------|------|--------------------------------------------|
  | 2026-04-26        | 25–29 % | Baseline real medido                     |
  | 2026-08-10 (COV-4.3) | **70 %** | CI/Codecov main ~78 %; catch-up seguro |
  | 2026-08-10 (post-5.9) | **80 %** | CI/Codecov main ~83.5 %; margen ≥3 pp |
  | Next (meta S-COV-85) | **85 %** | Objetivo sprint + Codecov target (COV-4.4) |

  > Subir el gate **después** de verde en main con margen; no saltar a un
  > umbral por encima del TOTAL medido.

- **Step adicional** "QAA suite — línea de defensa": corre
  `pytest tests/test_qaa_*.py -q --no-cov`. Es bloqueante e independiente del gate.
- **Codecov** (COV-4.4): `informational: false`, project `target: 85%` con
  `threshold: 7%` (margen ~78% actual). Patch `target: 50%`. Ver `codecov.yml`.
  Reducir threshold cuando main sostenga ≥85%.
- **Matriz / baseline docs** (COV-4.5): [`test-matrix.md`](test-matrix.md) ·
  `TESTING_RULES.md` §7.

### 2.4 `migrations`

- Aplica `alembic upgrade head` contra una base limpia y verifica que `alembic
  current` esté en `(head)`.
- Cubre las nuevas migraciones:
  - `alembic/versions/20260421_schema_hardening_ingestion.py`
  - `alembic/versions/20260421_trades_idempotency_columns.py`
  - `alembic/versions/20260424_merge_heads_trades_order_idx.py`
- **Cómo agregar una nueva migración**:
  1. `alembic revision -m "descripcion" --autogenerate` (revisar el diff).
  2. Editar la migración para que sea idempotente y reversible (`downgrade`).
  3. Confirmar que `alembic upgrade head` funciona en local con la BD vacía.
  4. Push → el job `migrations` la valida automáticamente.
  5. Si hay heads divergentes, crear un merge (`alembic merge -m "..."`).

### 2.5 `docker`

- Build de la imagen y push a GHCR (`ghcr.io/<owner>/grid-bot:<tag>`).
- Solo se ejecuta en eventos distintos de `pull_request`.
- Tags: `branch`, `sha-<short>`, `latest` (sólo `main`).
- Usa `cache-from`/`cache-to: type=gha` para builds incrementales.

### 2.6 `deploy`

- Sólo en `main` y eventos `push`.
- Requiere `HEROKU_API_KEY` y `HEROKU_APP_NAME`.
- Hace `docker tag` → `docker push registry.heroku.com/$APP/web` →
  `heroku container:release web`.
- Después del release, ejecuta `alembic upgrade head` en Heroku (no bloqueante:
  `|| true`).

---

## 3. Secrets requeridos en GitHub

| Secret | Uso | Dónde |
|---|---|---|
| `CODECOV_TOKEN` | Subir reportes de cobertura | Settings → Secrets → Actions |
| `HEROKU_API_KEY` | Login a Container Registry de Heroku | idem |
| `HEROKU_APP_NAME` | Nombre de la app destino | idem |
| `GITHUB_TOKEN` | Autoprovisto, para GHCR push | (no se setea) |

> Para variables públicas (no sensibles) usar `vars` en lugar de `secrets`.

---

## 4. Pre-commit local (`.pre-commit-config.yaml`)

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Hooks activos:

| Hook | Para qué |
|---|---|
| `check-added-large-files` | Bloquea archivos > 1 MB |
| `end-of-file-fixer` / `trailing-whitespace` | Higiene |
| `check-yaml` / `check-toml` / `check-merge-conflict` / `detect-private-key` | Higiene |
| `ruff` (`--fix`) + `ruff-format` | Linting + formateo (rápido) |
| `bandit` | Seguridad estática (mismo umbral que CI) |
| `detect-secrets` | Bloquea commits con keys/tokens |

> El baseline de `detect-secrets` está en `.secrets.baseline`. Para regenerarlo:
>
> ```bash
> detect-secrets scan > .secrets.baseline
> ```
>
> Revisar y commitear el archivo. Cualquier nueva detección bloquea el commit
> hasta que se justifique con `# pragma: allowlist secret` o se actualice el
> baseline.

---

## 5. Debug local de un fallo de CI

### 5.1 Falla `lint`

```bash
python -m pyflakes app
ruff check app tests --fix
```

### 5.2 Falla `security-scan`

```bash
bandit -r app --skip B101,B601 --severity-level medium --confidence-level medium -f txt
pip-audit -r requirements.txt
```

### 5.3 Falla `test` por gate de cobertura

```bash
pytest -q --cov=app --cov-report=term-missing
# El reporte muestra qué archivos están por debajo del umbral.
# Identificá un módulo P1 (alto impacto) y subí su cobertura primero.
```

### 5.4 Falla `test` por test específico

```bash
# Reproducí el test exacto con verbose:
pytest tests/test_<archivo>.py::<test> -vv -s

# Asegurate de las env vars que usa CI (ver §3 de TDD_WORKFLOW.md).
```

### 5.5 Falla `migrations`

```bash
# Levantar BD limpia local
docker compose --profile development up -d db
# Reemplazá ${DB_PASS} por la contraseña local del container (ver docker-compose.yml).
DATABASE_URL="postgresql://gridbot:${DB_PASS}@localhost:5432/gridbot_test" alembic upgrade head  # pragma: allowlist secret
DATABASE_URL=... alembic current
```

---

## 6. Cómo agregar nuevos skills de Antigravity al pipeline

1. Identificar el dolor (lentitud, falsos positivos, gap de cobertura).
2. Revisar el catálogo de skills (carpeta `.cursor/skills/` o el sitio de
   Antigravity).
3. Documentar **antes** del cambio en este runbook (§7) qué skill se va a
   adoptar y por qué.
4. Si el skill exige un step nuevo en CI, mantenerlo no bloqueante (`|| true`)
   por al menos 1 sprint para medir falsos positivos.
5. Después del periodo de prueba, retirarle el `|| true` y documentar el cambio
   en `AGENTS.md` (sección **Agentes de Calidad y CI/CD**).

---

## 7. Skills adoptados

| Fase | Skill | Estado |
|---|---|---|
| Diagnóstico | `@systematic-debugging`, `@find-bugs` | Adoptado |
| Reparación de tests | `@bug-hunter`, `@phase-gated-debugging` | Adoptado |
| TDD | `@tdd-orchestrator`, `@test-driven-development` | Adoptado |
| CI/CD | `@cicd-automation-workflow-automate`, `@github-actions-templates` | Adoptado |
| Documentación | `@documentation-generation-doc-generate`, `@agents-md` | Adoptado |
| Verificación | `@verification-before-completion`, `@lint-and-validate` | Adoptado |
| Ops watch | Ver [`OPS_WATCH_ANTIGRAVITY.md`](OPS_WATCH_ANTIGRAVITY.md) | Adoptado |

---

## 8. Métricas del pipeline (objetivo 2026)

| Métrica | Objetivo | Hoy |
|---|---|---|
| Duración total `lint + security + test` | < 8 min | ~6 min |
| Duración `docker` | < 5 min | ~4 min |
| Cobertura global | ≥ 85 % | 29 % (con plan a 85 %) |
| QAA pass rate | 100 % | 100 % (170/170) |
| Bandit findings (HIGH/CRIT) | 0 | 0 |
| pip-audit CVEs sin justificar | 0 | 0 |

Cualquier desviación se discute en el siguiente standup y se anota en
`reports/ops_watch/LATEST.md`.

---

## 9. Recreate paper-safe (no wipe Redis breakers)

Los circuit breakers L0 (SI REDUCE_ONLY) viven en Redis HASH `gridbot:breakers:v1`.
Recrear API/worker **no** debe tocar Redis ni Postgres.

```bash
docker compose -f docker-compose.local.yml up -d --build --force-recreate --no-deps api worker beat
```

Tras recreate:

1. `docker compose exec redis redis-cli TYPE gridbot:breakers:v1` → `hash`
2. `GET /breakers/summary` → `system_integrity` activo, `REDUCE_ONLY`
3. Grafana CEO: Freno = 1 **o** racha paper ≥ 5

Si `TYPE none` o `breaker_store_backend{job="gridbot-api",backend="memory"}==1` con racha ≥ 5:
el proceso debe fail-closed a REDUCE_ONLY y disparar `BreakerStoreMissingFailClosed`
(Grafana + Telegram). **No** `deactivate`. Policy de ambiente nuevo: default
`CB_EMPTY_STORE_POLICY=fail_closed` (nace bloqueado); `fresh` solo si Desk lo elige.
Wipe Redis: solo `GRIDBOT_ALLOW_BREAKER_STORE_WIPE=1` (nunca en paper).
Incidente 2026-08-30 y defensa C→B→A:
[`Docs/ops/rca-si-redis-hash-wipe-2026-08-30.md`](ops/rca-si-redis-hash-wipe-2026-08-30.md),
[`Docs/ops/breakers-process-scope.md`](ops/breakers-process-scope.md).
Simulacro `DEL` 2026-08-30T13:31:44Z: **PASS**
([`Docs/ops/smoke-breaker-del-fail-closed-2026-08-30.md`](ops/smoke-breaker-del-fail-closed-2026-08-30.md)).
Prueba SI 5×15 **intento 3** (firma Desk Lead 2026-09-09; paper `TRADING_ENABLED`):
[`Docs/ops/trial-si-5x15-2026-09-09.md`](ops/trial-si-5x15-2026-09-09.md) —
**CERRADO 2026-09-10 NO-GO** (idle 12 h sin close post-t0; SI REDUCE_ONLY; overlay revertido a N10).
Intentos 1–2 no son evidencia. No wipe de racha 19 / Redis HASH.

Beat: `--schedule /app/data/celerybeat-schedule` (persistente) y
`--pidfile=/tmp/celerybeat.pid` (no en el volumen: un pidfile stale crash-loopea
exit 73). Tras recreate beat: borrar solo `data/celerybeat.pid` si quedó de un
intento viejo; **no** borrar el schedule.

Detalle: [`Docs/ops/followup-logs-diagnostico-2026-08-28.md`](ops/followup-logs-diagnostico-2026-08-28.md).
