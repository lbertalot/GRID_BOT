# Spike — flip lectura ledger paper JSON → Postgres

**Fecha:** 2026-09-13  
**Owner:** `trading-dba` + `trading-engineering-manager` + Quant (lectura tear)  
**Modo:** paper-only · **PROMOTE_LIVE: NO** · **no ejecutar el flip en Pre-T0**  
**Addendum:** [ADR-016-addendum.md](ADR-016-addendum.md)

DoD DBA **antes** de dual-write o tests TDD que cambien la lectura de producción.

---

## 1. Inventario de esquema (`paper_ledger_*`)

Fuente: [`app/models/paper_ledger.py`](../../app/models/paper_ledger.py) + Alembic:

| Revisión | Tablas / delta |
|----------|----------------|
| `20260827_paper_ledger` | `paper_ledger_cycles`, `intents`, `reservations`, `fills` |
| `20260827_paper_ledger_full` | columnas fee/slippage/PnL en cycles/fills; `paper_ledger_accounts`; `paper_ledger_fill_cycles`; `paper_ledger_equity_samples` |

Índices **hoy** (ninguno `CONCURRENTLY`):

| Tabla | Índice |
|-------|--------|
| `paper_ledger_cycles` | PK `cycle_id`; `symbol` (`index=True`) |
| `paper_ledger_intents` | PK; `UNIQUE(client_order_id)` |
| `paper_ledger_reservations` | PK; `UNIQUE(intent_id, cycle_id)` |
| `paper_ledger_fills` | PK `fill_id`; FKs **sin** índice dedicado en `executed_at` / `intent_id` |
| `paper_ledger_equity_samples` | PK `sample_id`; `at` (`index=True`, creado **con** la tabla) |

`downgrade()` ya existe en ambas revisiones. Eso **no** sustituye un `down` de índices concurrentes nuevos.

## 2. Índices concurrentes (obligatorio antes de dual-write / TDD lectura)

Paper sigue sirviendo ticks: `CREATE INDEX` blocking no es aceptable. Propuesta (nombres estables):

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_paper_ledger_fills_executed_at
  ON paper_ledger_fills (executed_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_paper_ledger_fills_intent_id
  ON paper_ledger_fills (intent_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_paper_ledger_cycles_closed_at
  ON paper_ledger_cycles (closed_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_paper_ledger_cycles_symbol_closed_at
  ON paper_ledger_cycles (symbol, closed_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_paper_ledger_equity_samples_at_equity
  ON paper_ledger_equity_samples (at, equity);
```

Alembic: revisión **nueva** (no este spike) con `op.create_index(..., postgresql_concurrently=True)` y `transaction_per_migration` / `op.execute` fuera de transacción. **No mergear ni aplicar** hasta DBA + ensayo paper.

### Criterio de degradación

Ensayo: `EXPLAIN ANALYZE` de (a) fills por `executed_at` última ventana 30d, (b) samples por `at` para tear A2. Si p95 de esas lecturas **empeora >20%** vs baseline o el `CREATE INDEX CONCURRENTLY` corre >5 min en paper → **no** dual-write; ejecutar `down`.

## 3. Script `down` (rollback) — DoD testeado

Índices (no borrar tablas ADR):

```sql
DROP INDEX CONCURRENTLY IF EXISTS ix_paper_ledger_fills_executed_at;
DROP INDEX CONCURRENTLY IF EXISTS ix_paper_ledger_fills_intent_id;
DROP INDEX CONCURRENTLY IF EXISTS ix_paper_ledger_cycles_closed_at;
DROP INDEX CONCURRENTLY IF EXISTS ix_paper_ledger_cycles_symbol_closed_at;
DROP INDEX CONCURRENTLY IF EXISTS ix_paper_ledger_equity_samples_at_equity;
```

Ensayo Pre-T2 (DBA, paper):

1. Baseline `EXPLAIN ANALYZE` + tamaño índices (`pg_relation_size`).
2. `upgrade` concurrente.
3. Re-medir. Si degradación → `down` y verificar queries vuelven al plan previo.
4. Acta en este spike (fecha, p95 before/after). **Pendiente** hasta corrida DBA.

Alembic `downgrade` de `20260827_paper_ledger_full` **no** se usa como rollback de este spike: dropearía tablas y datos backfilleados.

## 4. Lectores a flippear (cuando Desk autorice)

| Path | Hoy | Post-flip |
|------|-----|-----------|
| `get_paper_ledger()` | JSON | PG `paper_ledger_accounts` + cycles/fills |
| `desk_tear_capa_a._load_json` | `paper_equity_ledger.json` + `paper_equity_series.json` | mismas tablas / `paper_ledger_equity_samples` |
| `get_paper_equity_series()` | JSON | samples PG **o** JSON+lock hasta T2 |

Orden: DBA índices+`down` → dual-write (JSON sigue SoT) → TDD lectura en fixture → go/no-go flip. **Este sprint se detiene antes del dual-write.**

## 5. Go / No-Go flip (T2)

| Go | No-Go |
|----|-------|
| Addendum publicado; índices CONCURRENTLY aplicados **o** explícitamente diferidos con acta; `down` ensayado | Claim «JSON=export» sin flip |
| Paridad JSON vs PG en window de ensayo (ciclos/fills/cash Decimal) | Dual-write sin índices ni rollback |
| Serie: lock Redis G18/G19 **o** samples en PG, decisión T2 | Mezclar O-3 con cobertura A2 |

**PROMOTE_LIVE: NO.** No iniciar OOS / Fase 2 desde este spike.
