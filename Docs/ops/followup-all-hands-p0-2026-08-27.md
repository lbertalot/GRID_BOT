# Follow-up P0 All Hands — 2026-08-27 (tarde)

**Modo:** paper-only · **PROMOTE_LIVE: NO** · `TRADING_ENABLED=false`  
**Acta:** `Docs/product/ALL-HANDS-L0-ACTA-2026-08-27.md`  
**No** se reabrió el grid. **No** se tocó spacing/sizing. **No** N11.

## Hecho

### 1. Recreate paper-safe → HEAD

| Pieza | Antes | Después |
|-------|--------|---------|
| `gridbot_api` / `worker` started | 2026-08-26T18:41:48Z | **2026-08-27T16:53:03Z** |
| `/health` | paper | paper · `force_real_mode=false` · `trading_enabled=false` · `live_gate_signed=false` |
| Runtime hash (`resolve_grid_config_hash`) | env `ff6a35fc…` | env + sidecar **`ff6a35fc…7f5c4`** (coinciden) |

Compose: `up -d --build --force-recreate --no-deps api worker beat`. **No** se recreó db/redis (ledger PG intacto).

### 2. SI HOLD restaurado (D3)

Redis `gridbot:breakers:v1` estaba `TYPE none` (pérdida post-recreate previo). Restaurado **después** del recreate de hoy para que persista.

| Campo | Valor |
|-------|--------|
| API `/breakers/summary` | `active_breakers=["system_integrity"]` |
| `operational_state` | **REDUCE_ONLY** |
| reason | `Demasiadas pérdidas consecutivas: 19 (All Hands D3 restore HOLD; redis miss post-recreate 2026-08-27)` |
| ts | 2026-08-27T16:54:50Z |
| Redis | HASH persistido (no memory-only) |

Esto **no** es override ni permiso de operar. `TRADING_ENABLED` sigue `false`.

### 3. Hash last≠expected — **no alineado** (sin N11)

| Store | Hash |
|-------|------|
| Sidecar + `.env` + runtime resolve | `ff6a35fc…7f5c4` |
| Samples PG (81) / tear 00:45Z | `ac1cb596…` (serie internamente única) |

No se reescribieron samples ni se disparó snapshot de alineación: un sample nuevo con `ff6a35fc` **rompería A1** (dos hashes en la misma ventana). G8 sigue **ROJO** hasta decisión desk (N11 vs aceptar last de serie vs freeze script).

## Pendiente (sigue siendo 2026-08-28)

- Tear Capa A post-HEAD con SoT **Postgres**: `desk_tear_capa_a.py` todavía hardcodea `paper_equity_ledger.json`. Regenerar hoy seguiría siendo T0.3 JSON.
- G8 hash / A1 de ventana.
- Confirmar que el próximo recreate **no** borre Redis breakers (ya volvió a pasar una vez).

## Won't

Live · `FORCE_REAL_MODE` · `TRADING_ENABLED=true` · reset SI para fills · wipe · bajar spacing · concatenar 19 RT como edge.
