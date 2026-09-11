# Dossier LIVE-READY / NO-GO — cerrado (2026-09-11)

**Veredicto:** **NO-GO live**  
**Modo:** paper-only · **PROMOTE_LIVE: NO** · Cursor **no** firma LIVE_GATE ni DL-4  
**Cerrado:** 2026-09-11T20:42Z (evidencia runtime + SoT + pytest)

Fuentes: [validation-paper-tablero-2026-09-10.md](validation-paper-tablero-2026-09-10.md) · [tear-sheet-paper-30d-fase0-2026-09-10.md](tear-sheet-paper-30d-fase0-2026-09-10.md) · [trial-si-5x15-2026-09-09.md](trial-si-5x15-2026-09-09.md) §8 · [rca-gap126h-hash-drift-2026-09-11.md](rca-gap126h-hash-drift-2026-09-11.md) · [o3-alerts-e2e-procedure-2026-09-11.md](o3-alerts-e2e-procedure-2026-09-11.md) · [emergency-stop-e2e-host-checklist-2026-09-11.md](emergency-stop-e2e-host-checklist-2026-09-11.md) · [RUNBOOK_BINANCE_IP_ALLOWLIST.md](RUNBOOK_BINANCE_IP_ALLOWLIST.md) · [fase1-action-plan-2026-09-15.md](fase1-action-plan-2026-09-15.md) · [fase2-gate-2026-09-22.md](fase2-gate-2026-09-22.md) · [LIVE_CHECKLIST.md](../LIVE_CHECKLIST.md) · [LIVE_GATE_TEMPLATE.md](../gates/LIVE_GATE_TEMPLATE.md).

**Insumo firma Desk Lead 14-sep:** este dossier + tear Fase 0 + RCA gap/hash. Cursor **no** adelanta `ITERATE`/`REJECT` de Fase 0.

---

## PASO 0 — Prueba 5×15 (resuelto)

| Intento | Acta | Estado |
|---------|------|--------|
| 1 | trial-si-5x15-2026-08-29 | **ABORTADA** (wipe HASH) |
| 2 | trial-si-5x15-2026-08-30 | **NO-GO** (0 closes) |
| 3 | trial-si-5x15-2026-09-09 §8 | **CERRADO — NO-GO prueba** (2026-09-10); idle 12 h; overlay → N10 |

**Resolución PASO 0 = (b):** el §8 es **cierre formal con acta** y decisión Desk Lead «NO-GO prueba». No hay trial activo (`PAPER_TRIAL_*` unset). SI OPEN = residuo documentado (**no** resetear / no wipe / no segundo override).

Si Desk Lead hubiera querido **(a)** (esperar otro 5×15), debe anular explícitamente este dossier; hasta entonces se procede con Fase 0 paper hacia **NO-GO live**.

---

## T0.5 frescura (2026-09-11T20:42Z)

| Señal | Valor |
|-------|--------|
| `/health` | `effective_mode=paper` · `paper_trading=true` · `trading_enabled=false` · `force_real_mode=false` · `live_gate_signed=false` · `emergency_stop=false` |
| `active_breakers` | `["system_integrity"]` |
| SI reason | Override expiró sin close post-t0 · REDUCE_ONLY · **NO-GO prueba** |
| SI `activated_at` | `2026-09-10T07:13:22.645098` |
| leftover `operational_state` | `CLOSED` (copy normaliza; breaker **no** mutado) |
| Equity SoT | 999.0232991152 (E0=1000 · PnL −0.9767) |

---

## SoT ledger / serie (read-only, 2026-09-11T20:40Z)

| Señal | Valor |
|-------|--------|
| Samples / daily_close | 580 / **27** (hace falta ≥30) |
| Gaps &gt;2 h | **17** (max ~126 h) → A2 **FAIL** |
| Ciclos cerrados / post-t0 5×15 | 19 / **0** |
| Hash en serie | `ac1cb596…` (único en samples) |
| Sidecar N10 | `ff6a35fc…` → drift last≠expected (MM OFF_TRACK) |
| Fills / con `client_order_id` | 38 / **0** (fix coid = fills nuevos) |
| RCA gap 126 h + hash drift | [rca-gap126h-hash-drift-2026-09-11.md](rca-gap126h-hash-drift-2026-09-11.md) — gap = stack offline 04→09-sep; drift = sticky pre-qty-fix (no config pirateada en fills) |

---

## RCA resueltos (contexto para firma 14-sep — no reabrir)

Fuente: [rca-gap126h-hash-drift-2026-09-11.md](rca-gap126h-hash-drift-2026-09-11.md).

| Hallazgo | Veredicto cerrado | Severidad |
|----------|-------------------|-----------|
| Gap **126.07 h** `2026-09-04T11:07:22Z`→`2026-09-09T17:11:26Z` | Stack/host offline (logs/health/Redis StartedAt); **no** es beat 28-ago ni Redis DEL 30-ago | **P1 A2** |
| Hash `ac1cb596…` vs sidecar `ff6a35fc…` | Sticky pre-qty-fix; fills 38/38 = `0.0082`; A1 auto PASS en falso 27-ago→11-sep | **P0 instrumentación A1** (no P0 ejecución) |
| Fix A/B (resolve en sample) | Aplicado 11-sep; samples nuevos = expected; históricos no reescritos | — |
| Fix E (A1 exige hash==expected) | **APLICADO** 2026-09-11 — A1 auto + `config_is_frozen` fallan si único ≠ expected | — |

---

## Fase 0 — paper close (ventana hasta 14-sep)

**Firma DL-4:** exclusiva Desk Lead el 14-sep (`ITERATE` \| `REJECT`). Cursor **no** firma ni recomienda el veredicto de cierre.

| Ítem | Estado |
|------|--------|
| Ventana canónica | 2026-08-15 → 2026-09-14 UTC |
| Evidencia tear / SoT / RCA | Lista arriba + tear-sheet-paper-30d-fase0 |
| PROMOTE_PAPER / PROMOTE_LIVE | **NO** hasta (y salvo) decisión humana explícita |

---

## Fase 1 — auditoría (inventario 2026-09-11)

Arranque planificado 2026-09-15. Adelantos del hotfix (no rehacer):

| Must | Estado |
|------|--------|
| R-2 SEC OFF paper | Hecho (tests) |
| Q-3 / QA-4 Capa A spec | Hecho (`test_desk_tear_capa_a_spec`) |
| DL-2 / T-2 trial NO-GO + N10 | Hecho |
| A1 hash punta a punta | **Fix E APLICADO** (único == expected); serie histórica sticky → A1 FAIL honesto |
| R-6 key sin withdraw | Runbook listo ([RUNBOOK](RUNBOOK_BINANCE_IP_ALLOWLIST.md) + breakers-process-scope); **ejecución 2FA = humano** |
| O-3 alertas disparan y llegan | Procedimiento [o3-…](o3-alerts-e2e-procedure-2026-09-11.md); path E2E probado smoke 30-ago; stale fresco = **OK Desk** |
| QA-5 QAA | **185 passed**, 25 skipped (2026-09-11T20:42Z) |

Won't Fase 1: live, wipe, segundo 5×15, capital &gt;200.

---

## Fase 2 — paper OOS

**BLOQUEADA** ([fase2-gate-2026-09-22.md](fase2-gate-2026-09-22.md)): requiere firma Fase 0 + A1–A8 medibles en freeze nuevo. Overlay 5×15 no es candidata. **No iniciar OOS.**

---

## Checklist LIVE_GATE (ítems 1–8)

| # | Requisito | Estado | Evidencia / hueco |
|---|-----------|--------|-------------------|
| 1 | Tear paper umbrales OK | **ROJO (evidencia)** | A2 FAIL (gap 126 h + otros); PnL &lt;0; ciclos 19≪120 — Desk decide el 14-sep |
| 2 | Tests integridad | **OK código** | Fix E A1 + contrato hash A/B + QAA; ver pytest abajo |
| 3 | EMERGENCY_STOP / TRADING_ENABLED cortan real | **PARCIAL** | Unit OK; E2E host = [checklist](emergency-stop-e2e-host-checklist-2026-09-11.md) **requiere Desk** |
| 4 | Observabilidad | **PARCIAL→DOC** | Reglas Prom cargadas; path Telegram vía smoke 30-ago; O-3 stale = OK Desk |
| 5 | Secrets + key sin withdraw | **PENDIENTE humano** | Runbook R-6/IP listo; 2FA humano |
| 6 | Rollback `--no-deps` | **DOC OK** | `breakers-process-scope.md` |
| 7 | live-status NO-GO | **OK esperado** | `live_gate_signed=false` |
| 8 | RISK_OK + capital/pérdida | **BLOQUEADO humano** | Placeholders 600/30 |

### Solo acción humana (bloquean live, no el paper close)

- R-6 / IP allowlist + withdraw OFF (2FA).
- Firma dual CEO + Desk Lead + artefacto `LIVE_GATE_*.md`.
- Frase `autorizo live en Binance spot con capital <X>`.
- E2E EMERGENCY_STOP en host (checklist).
- Opcional: disparo fresco `PaperSnapshotStale20m` (impacto A2).

### Técnicamente resuelto / documentado en este ciclo

- RCA gap 126 h + hash sticky (veredictos cerrados).
- Fix A/B hash en samples (`resolve_grid_config_hash`).
- **Fix E:** A1 + `config_is_frozen` exigen `hash == GRID_CONFIG_HASH|sidecar` (regresión sticky≠expected → FAIL).
- Procedimiento O-3 + evidencia reglas Prom + smoke path.
- Runbook R-6/IP sin ambigüedad withdraw vs IP.
- Checklist EMERGENCY_STOP E2E host (ejecución = Desk).

Firma dual CEO + Desk Lead: **NO**. Artefacto `LIVE_GATE_YYYYMMDD.md`: **NO**.  
Frase `autorizo live…`: **NO**.

---

## Pytest (evidencia)

```bash
# Suite gate (previa): 109 passed — telegram SI, breakers, defense, order guard, recon, docker DoD, …
# QAA + secret redaction + fase0 + Capa A (2026-09-11T20:42Z):
/usr/local/bin/python3.11 -m pytest tests/test_qaa_*.py \
  tests/test_log_secret_redaction.py tests/test_fase0_close_checklist.py \
  tests/test_desk_tear_capa_a_spec.py -q
# → 185 passed, 25 skipped
```

Invariantes post-suite: `PAPER_TRADING=true` · `TRADING_ENABLED=false` · `FORCE_REAL_MODE` vacío · SI NO-GO **intacta**.

---

## Veredicto live (no es firma Fase 0)

**NO-GO live** — evidencia suficiente; **PROMOTE_LIVE: NO**.

La firma paper Fase 0 (`ITERATE`/`REJECT`) es **solo** Desk Lead el 14-sep con ventana cerrada. Este dossier no la sustituye.

Motivos live (cualquiera basta): tear/A2 rojo, SI OPEN residuo NO-GO, sin frase `autorizo live…`, sin firmas duales, capital piloto no confirmado.

**PROMOTE_LIVE: NO.** No `FORCE_REAL_MODE`. No wipe. No Telegram real en tests. Agente no firma LIVE_GATE ni DL-4.
