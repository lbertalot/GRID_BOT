# Ops ledger — persistencia (B19 / ADR-008)

Paper-safe. Sin migraciones Alembic. El committed del ledger alimenta `tradable_capital` y el kill floor: perder el archivo es un incidente de riesgo, no solo de contabilidad.

## Veredicto DBA: JSON vs Postgres

| Opción | Estado | Cuándo |
|--------|--------|--------|
| **JSON versionado** (`JsonOpsLedgerStore`) | **Go P0** | ADR-008 autoriza “tabla **o** JSON versionado”. Volumen bajo (pocas filas/mes), escritura atómica, `OpsLedgerStore` abstrae el backend. |
| **Postgres** | Diferido P1 | Misma API de store; una sola migración Alembic cuando haya gasto real sostenido o multi-réplica. |

**No** usar Redis como SoT del ledger (TTL / no auditoría de fills de ops). Postgres no es bloqueante para cerrar B19 en paper local.

## Contrato de path

| Contexto | `OPS_LEDGER_PATH` | Persistencia |
|----------|-------------------|--------------|
| Default / host sin Docker | `data/ops_ledger.json` (relativo a `WORKDIR=/app`) | Disco del host; seed vacío en repo (`data/ops_ledger.json`) |
| **Docker Compose local** | `/var/lib/gridbot/ops/ops_ledger.json` | Volume nombrado **`ops_ledger_data`** → `/var/lib/gridbot/ops` |
| Heroku dyno | (mismo path o default) | **FS efímero** — ver abajo |

Formato en disco (schema v1):

```json
{"version": 1, "currency": "USD", "entries": [{"date": "YYYY-MM-DD", "category": "vps|data|llm|other", "amount_usd": "12.50", "note": "..."}]}
```

Importe siempre string/`Decimal` (nunca float). Escritura atómica: `*.tmp` + `os.replace`.

### Compose (recomendación wireada en B19)

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

## Heroku / ephemeral

Los dynos Heroku **no** conservan disco entre restart/redeploy. Con `OPS_LEDGER_PATH` en el filesystem del slug/dyno, el burn se pierde y el kill floor queda desalineado (blocker B19).

Hasta Postgres P1 (o mount externo / Object storage + sync):

- Paper en Heroku: **no registrar gasto real** que mueva `ops_reserve_committed`, o
- Apuntar el path a almacenamiento no efímero fuera del dyno.

Neon/Postgres del add-on **no** sustituye automáticamente este JSON: hace falta implementación `PostgresOpsLedgerStore` + migración.

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
- Sin Alembic que revertir en este slice.
