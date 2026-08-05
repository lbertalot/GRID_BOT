# Ops ledger — persistencia (B19 / ADR-008)

Paper-safe. **Sin migraciones Alembic en este documento** (P0 cerrado; P1 es diseño + go/no-go). El committed del ledger alimenta `tradable_capital` y el kill floor: perder el archivo es un incidente de riesgo, no solo de contabilidad.

B19 (volume JSON) ya en `main` (#60). Esta nota fija el veredicto DBA P1: cuándo el JSON basta y cuándo Heroku obliga a Postgres.

## Veredicto DBA: JSON vs Postgres

| Opción | Estado | Cuándo |
|--------|--------|--------|
| **JSON versionado** (`JsonOpsLedgerStore`) | **Go P0** | ADR-008 autoriza “tabla **o** JSON versionado”. Volumen bajo (pocas filas/mes), escritura atómica, `OpsLedgerStore` abstrae el backend. |
| **Compose volume `ops_ledger_data`** | **OK paper local** | Persistencia durable entre recreate/`down` sin `-v`. Suficiente para paper L0 en máquina local. |
| **JSON en FS del dyno Heroku** | **No-go** | Disco efímero: no registrar gasto real que mueva kill floor. Ver § P1. |
| **Postgres** (`PostgresOpsLedgerStore`) | **P1** | Mismo protocolo `OpsLedgerStore`; implementación + Alembic **cuando** se active P1 (no ahora). |

**No** usar Redis como SoT del ledger (TTL / no auditoría de fills de ops). Postgres no es bloqueante para paper local con Compose.

## P1 — Heroku efímero → Postgres (mismo `OpsLedgerStore`)

### Go / no-go operativo

| Entorno | Persistencia | Registrar gasto que mueva `ops_reserve_committed` / kill floor |
|---------|--------------|----------------------------------------------------------------|
| Docker Compose local + volume `ops_ledger_data` | Durable (sobrevive recreate sin `-v`) | **Go** paper local |
| Host path / bind controlado con backup | Durable si el path no se borra | **Go** paper con disciplina de backup |
| **Heroku dyno FS** (`OPS_LEDGER_PATH` en slug/ephemeral) | **Efímero** (restart/redeploy/ciclo de sleep pierden el archivo) | **No-go** — no registrar gasto real |

**No-go Heroku (explícito):** mientras el SoT sea JSON en el filesystem del dyno, **está prohibido** registrar gasto real de ops que reduzca `ops_reserve_committed` y por tanto desplace el kill floor / `tradable_capital`. Un restart silencioso dejaría el burn en cero y el floor sobreestimado → riesgo de liquidar el book con datos falsos.

Mitigaciones válidas **antes** de P1 code:

1. No POST-ear entries de gasto real en Heroku; llevar el burn solo en paper local con volume, o
2. Almacenamiento no efímero fuera del dyno (object store + sync) — fuera de alcance de este slice; o
3. Activar P1 Postgres (abajo).

### Contrato de store (sin cambiar dominio)

```text
OpsLedgerStore (Protocol)          # app/core/ops_ledger.py
  read_all()  -> list[dict]
  write_all(rows) -> None

JsonOpsLedgerStore     # P0 — archivo versionado
PostgresOpsLedgerStore # P1 — misma API; filas en Postgres
```

`OpsLedger` y las rutas `/api/ops/ledger` **no** deben acoplarse al backend: inyectar el store vía factory (`get_ops_ledger` / env). P1 = nueva implementación del Protocol, no fork del dominio.

### Diseño Postgres P1 (deferred — **sin Alembic ahora**)

Cuando se autorice implementación:

| Pieza | Nota DBA |
|-------|----------|
| Tabla sugerida | `ops_ledger_entries` (o equivalente) con `date`, `category`, `amount_usd Numeric`, `note`, `created_at`, PK |
| Tipos | `Numeric`/`Decimal` para montos — **nunca** `float` / `double` |
| Índices | `(date)`, opcional `(date, category)` para listados MTD |
| Escritura | Transacción; `write_all` puede ser replace-set o upsert idempotente por id de entry — decidir en ADR de implementación |
| SoT | Postgres es la fuente de verdad; Redis **no** cachea balances de ops como SoT |
| Migración | **Una** revisión Alembic reversible cuando se abra el slice de código P1 — **esta nota no la crea** |
| Cutover Heroku | `DATABASE_URL` / Neon add-on + `OPS_LEDGER_BACKEND=postgres` (nombre tentativo) → factory elige `PostgresOpsLedgerStore` |

Neon/Postgres del add-on **no** sustituye el JSON automáticamente: hace falta `PostgresOpsLedgerStore` + migración. Hasta entonces, Heroku = no-go para gasto real que mueva kill floor.

### Criterio de activación P1 (código)

Abrir slice de implementación cuando ocurra **cualquiera**:

1. Necesidad de registrar burn real en Heroku (o multi-dyno / multi-réplica), o
2. Gasto sostenido / auditoría que requiera query SQL y backups de DB unificados, o
3. Decisión explícita del desk de promover el ledger fuera del volume Compose.

Fuera de esos triggers: JSON + Compose volume permanece **Go** paper local.

## Contrato de path (P0)

| Contexto | `OPS_LEDGER_PATH` | Persistencia |
|----------|-------------------|--------------|
| Default / host sin Docker | `data/ops_ledger.json` (relativo a `WORKDIR=/app`) | Disco del host; seed vacío en repo (`data/ops_ledger.json`) |
| **Docker Compose local** | `/var/lib/gridbot/ops/ops_ledger.json` | Volume nombrado **`ops_ledger_data`** → `/var/lib/gridbot/ops` — **OK paper local** |
| Heroku dyno | (mismo path o default) | **FS efímero** — **no-go** gasto real (ver § P1) |

Formato en disco (schema v1):

```json
{"version": 1, "currency": "USD", "entries": [{"date": "YYYY-MM-DD", "category": "vps|data|llm|other", "amount_usd": "12.50", "note": "..."}]}
```

Importe siempre string/`Decimal` (nunca float). Escritura atómica: `*.tmp` + `os.replace`.

### Compose (wireado en B19 / #60)

En `docker-compose.local.yml` y `docker-compose.yml`:

```yaml
# x-app-env
OPS_LEDGER_PATH: /var/lib/gridbot/ops/ops_ledger.json

# x-app-volumes
- ops_ledger_data:/var/lib/gridbot/ops

# top-level volumes
ops_ledger_data:
```

**No** confiar solo en el bind `./data:/app/data` para el ledger: convive con otros artefactos, se comparte entre stacks `-p` del mismo checkout, y no aísla el kill-floor data. El volume nombrado sobrevive `docker compose down` **sin** `-v`; `down -v` lo borra a propósito.

## Backup

1. **Local Compose:** `docker run --rm -v <proyecto>_ops_ledger_data:/src -v "$PWD:/dst" alpine tar czf /dst/ops_ledger_backup_$(date +%F).tgz -C /src .`
2. **Host path:** copiar `data/ops_ledger.json` (o el path configurado) a backup versionado fuera del repo de runtime.
3. Frecuencia: antes de `compose down -v`, cambio de máquina, o registro de gasto ≥ cap mensual.
4. Restore: detener api/worker que escriban el ledger → restaurar archivo en el mount → reiniciar → smoke survival.

## Test de supervivencia (restart)

**Unit (CI):** `tests/test_ops_ledger.py` — `test_ops_ledger_survives_restart_same_path` y `test_ops_ledger_survives_subprocess_reopen` (mismo path, nuevo proceso/store → burn/committed intactos).

**Manual Compose (paper):**

```bash
# 1) Registrar un gasto de prueba vía API (auth) o seed controlado en el volume
# 2) Recreate sin borrar volumes
docker compose -f docker-compose.local.yml up -d --force-recreate api
# 3) Verificar que el entry sigue
curl -sf -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/ops/ledger" | jq '.entries | length'
# Esperado: misma cantidad / mismo amount_usd que antes del recreate
```

Go si el burn y `ops_reserve_committed` coinciden pre/post recreate. No-go si el JSON vuelve vacío tras recreate **sin** `-v`.

## Rollback

- Quitar override de `OPS_LEDGER_PATH` / volume → vuelve el default `data/ops_ledger.json` (bind `./data`); **no** migra entradas automáticamente entre paths.
- Borrar volume: `docker compose … down -v` o `docker volume rm …_ops_ledger_data` — solo con backup previo.
- **Este slice (nota P1):** solo documentación — no hay migración Alembic ni `PostgresOpsLedgerStore` que revertir.
- Cuando exista P1 código: downgrade Alembic + factory de vuelta a `JsonOpsLedgerStore`; export SQL → JSON antes del cutback.
