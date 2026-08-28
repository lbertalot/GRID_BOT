# Follow-up diagnóstico logs — 2026-08-28

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Fuente:** [`DIAGNOSTICO_LOGS_2026-08-28.md`](../../DIAGNOSTICO_LOGS_2026-08-28.md)  
**Filtro:** All Hands D3 + freeze L0 (spacing 100 bps, sizing 200, ETHUSDT).  
**Tear del día:** [`tear-capa-a-2026-08-28.md`](tear-capa-a-2026-08-28.md) (A7 FAIL = SI abierto — esperado).

## Estado runtime (verificado)

| Check | Valor |
|-------|--------|
| `/health` | paper · `trading_enabled=false` · `force_real_mode=false` |
| SI API | `system_integrity` activo · `REDUCE_ONLY` · racha 19 |
| Redis `gridbot:breakers:v1` | HASH persistido |
| Tear A4 | E_last ≈ 999.02 MtM ≠ edge |
| Tear A8 | 19 ciclos cerrados / 38 fills |

**Veto:** no reset SI · no bajar spacing · no subir `MAX_CONSECUTIVE_LOSSES` · no `MIN_DECISION_CONFIDENCE` 0.75.

## Hallazgos Docker → go/no-go

| Ítem | Veredicto | Owner |
|------|-----------|--------|
| C1 racha 19 / SI | **HOLD D3** — racha legítima (19 RT net&lt;0). No reabrir grid. | desk-lead · prop · MM |
| C2 Redis/beat | **DONE 18:21 ART** — pidfile `/tmp`; beat healthy; ver [`exec-ola0-beat-pidfile-2026-08-28.md`](exec-ola0-beat-pidfile-2026-08-28.md) | devops |
| C3 Celery 6.0 | **ITERATE** — flag explícito en `celery_app` | backend-tdd |
| A4 logs 6×/ciclo | **ITERATE** — banners de boot, no 6 ciclos reales | backend-tdd |
| A5 confianza 0.60 | **DEFER umbral** — fallback ML RANGE; no subir corte | product (defer) |
| A6 GENERIC ATR | **ITERATE** — pasar símbolo freeze; no sustituir sizing 10×20 | backend-tdd |
| M7 errors.log 23d | **ITERATE** — rotación ya en handler; archivar legado a mano | devops |
| M8 ROI 0.18% / invested ~8879 | **No SoT** — métrica ops Binance ≠ equity paper ~999 | quant |
| M9 Diario=0 vs Total | **Esperado** bajo HOLD (último close 26-ago) | quant |
| B10 SQLAlchemy x2 | **ITERATE** — doble `configure_` | backend-tdd |
| B11 Telegram sin TZ | **ITERATE** — stamp UTC en copy CEO | backend-tdd |
| B12 ciclo ~1.3s | **OK** — no acción | — |
| B13 1 activo USDT | **OK** — HOLD | MM |

## Recreate paper-safe (no wipe Redis)

```bash
docker compose -f docker-compose.local.yml up -d --build --force-recreate --no-deps api worker beat
```

**Nunca** recrear `redis`/`db` para “limpiar logs”. Tras recreate: `TYPE gridbot:breakers:v1` debe ser `hash` y `/breakers/summary` debe seguir con SI. Si `TYPE none` → rehidratar REDUCE_ONLY (no `deactivate`).

## Archivo errors.log legado

Si `logs/errors.log` solo tiene líneas de 2026-08-05 (credenciales dummy):

```bash
mkdir -p logs/archive
mv logs/errors.log logs/archive/errors.log.20260805.bak
```

RotatingFileHandler (10 MB × 3–5) cubre el archivo nuevo. No borrar ledger ni telemetry.

## Veredicto

**ITERATE paper.** Revenue/live: **NO-GO.** **PROMOTE_LIVE: NO.**

**ROI ops ≠ edge paper:** `profit≈15.68 / invested≈8879 / roi≈0.18%` es métrica Binance histórica, no Capa A (equity ~999, freeze 10×20).
