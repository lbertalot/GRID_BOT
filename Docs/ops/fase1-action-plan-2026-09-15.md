# Fase 1 — auditoría y corrección (2026-09-15 → 2026-09-21)

**Arranque:** 2026-09-15 UTC (después del cierre de ventana 30d).  
**Modo:** paper-only · **PROMOTE_LIVE: NO** · no wipe Redis/ledger/rachas.  
**Tablero:** [validation-paper-tablero-2026-09-10.md](validation-paper-tablero-2026-09-10.md)

No optimizar spacing/niveles con datos de la ventana 08-15→09-14. Máximo **una** variante congelada para Fase 2.

---

## Ya adelantado el 2026-09-10 (no rehacer)

| Ítem | Qué | Tests |
|------|-----|-------|
| R-2 | SEC OFF solo si `effective_mode≠paper` o `FORCE_REAL_MODE` | `test_collect_sec_on_when_paper_cycle_enabled` |
| Q-3 / QA-4 | Auto Capa A alineada al spec (A1 único hash, A3 recon Decimal, A5 commission, A8 paper) | `tests/test_desk_tear_capa_a_spec.py` |
| DL-2 / T-2 | Trial 5×15 **NO-GO**; overlay revertido a N10; `TRADING_ENABLED=false` | compose + `/health` |

No revertir esos cambios. No `deactivate` SI mientras el reason sea el NO-GO de la prueba.

---

## Must (15–21 sep)

### 1. Hash A1 real (MM + Quant + TS) — TDD Decimal no aplica; hash es string

**Problema:** serie 501 samples con `ac1cb596…`; sidecar N10 `ff6a35fc…`; env runtime ya N10 post-cierre. MM seguirá `OFF_TRACK` mientras last≠expected.

**No hacer:** reescribir samples históricos ni wipe serie.

**Hacer:**

1. Test: `PaperEquitySeries.config_is_frozen()` sobre fixture con 2 hashes → False; con 1 → True.
2. Documentar en el acta 14-sep que la ventana 30d **no** es evidencia del freeze N10 (advisory 2026-08-26 + este drift).
3. DL-5: para Fase 2, **un** `GRID_CONFIG_HASH` en `.env` local = sidecar del JSON que realmente ejecuta el worker. Candidata por defecto: **N10 10×20 100 bps** (`ff6a35fc…`). El overlay 5×15 **no** es candidata (0 closes).
4. Nueva serie/ledger **solo** si Desk firma reinicio de ventana (N11). Si se reinicia: archivar bajo `paper_telemetry/archive/` — no borrar.

**Gate:** un hash punta a punta en la **siguiente** ventana; expected env = last sample.

### 2. T-3 client_order_id + fees (Trading Systems) — TDD Decimal

Evidencia Fase 0: 38/38 fills con fee; **0** `client_order_id` persistidos.

1. RED: test que `PaperFill` / persistencia exige `client_order_id` no vacío en fill paper.
2. GREEN: cablear el id idempotente ya usado en el executor.
3. No cambiar sizing.

**Gate:** 100% fills con `commission_usdt` y `client_order_id`; 0 duplicados.

### 3. T-4 identidad SoT — Decimal

Test: `|E − (cash + Σ qty·mid)| / E ≤ 0.001` en fixture con `Decimal`.  
Runtime ya pasa en el último sample (inv=0). Completar A3 en ticks con inventario ≠ 0.

### 4. Q-4 hipótesis tendencia (Quant, offline)

Comparar grid N10 vs buy&hold ETHUSDT spot **offline**, mismos 24 bps RT, misma ventana. Un notebook/CSV en `Docs/ops/research/`. No código de ejecución. No elegir 5×15 como variante (no validó).

### 5. R-4 / R-5 fail-closed y runbook (Risk)

Extender [breakers-process-scope.md](breakers-process-scope.md) con: stop de emergencia, ticker caído, Postgres caído, recreate `--no-deps` only.  
Tests existentes `test_breaker_store_defense_cba.py` / `test_s_breakers_b1_b4.py` — no bajar cobertura.  
R-6: checklist humano “API key sin retiro” (no pegar la key).

### 6. O-3 alertas accionables (SRE)

No duplicar reglas. Verificar que disparan y llegan: `HighDailyDrawdown`, `CircuitBreakerActivated`, `ReconciliationDiscrepancyDetected`, `CeleryWorkerDown` / `GridbotCeleryWorkersZero`, `PaperSnapshotStale20m`, `BreakerStoreMissingFailClosed`.  
Digest diario = sección del tablero (O-2 ya cubierto).

### 7. QA-5

```bash
/usr/local/bin/python3.11 -m pytest tests/test_qaa_*.py tests/test_breaker_*.py \
  tests/test_log_secret_redaction.py tests/test_desk_tear_capa_a_spec.py -q
```

Decimal en todo path financiero nuevo.

---

## Won't (Fase 1)

- `FORCE_REAL_MODE`, live, capital &gt; 200, piloto 600.
- Segundo overlay 5×15 o bajar spacing.
- Wipe Redis `gridbot:breakers:v1`, reset racha 19, borrar ledger.
- Relajar umbrales Capa B después de ver los datos.

---

## Salida

Config candidata documentada + hash sidecar + `.env` local (no git) + acta Desk: listo para Fase 2 (2026-09-22) **solo** si Capa A del nuevo freeze es medible.  
Gate: [fase2-gate-2026-09-22.md](fase2-gate-2026-09-22.md) — **no iniciar OOS ahora**.  
**PROMOTE_LIVE: NO.**
