# Acta — L0_DAY0_WINDOW_GO

**Fecha UTC de firma:** 2026-08-14  
**T0 canónico:** **2026-08-15 00:00 UTC**  
**Go-live candidato:** **2026-09-15** (`T0 + 31 días`)  
**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Esta acta no autoriza live ni `FORCE_REAL_MODE`.**

Plantilla: `Docs/L0_PAPER_FREEZE_PARAMS.md` §4.3.  
Política: `Docs/squad/desk-policy-l0.md` v2 §6.  
Tear de evidencia: `Docs/ops/tear-capa-a-2026-08-14-eod-sim.md`.

---

## 4.3 Veredicto

```
Fecha UTC: 2026-08-14 (firma) · T0 2026-08-15 00:00 UTC
config_hash: 630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f
E_0 (cierre de referencia post-N10): 1000.00 USDT
deployed_capital: 200
effective_mode: paper
primer_tick_at: 2026-08-13T23:10:59.495345+00:00 (post reset N10; no cuenta como día 1 de Capa B)

Veredicto: L0_DAY0_WINDOW_GO
Razones / owner gaps: ver §Gaps
Firmas: Desk Lead  trading-desk-lead  Market Maker  trader-market-maker (freeze L0-A)
```

---

## Hechos al corte 2026-08-14 18:20 UTC

| Campo | Valor |
|-------|--------|
| Hash freeze = sidecar | `630abf63…` PASS (A1) |
| `GRID_CONFIG_FILE` (runtime) | `grid_config_paper_l0.json` |
| `DESK_WINDOW_DAY0_ANCHOR` | **2026-08-15** (compose + `.env` + fallback código) |
| `effective_mode` | paper · `FORCE_REAL_MODE` vacío · e-stop false |
| Breakers | ninguno abierto (A7) |
| Equity / cash / inventario | 999.940935952 / 989.987959952 / 9.952976 |
| Identidad A3 `\|E − (cash+inv)\|` | **0** |
| Fills / fees | 1 BUY / 0.01000004 USDT → **A8 PASS** |
| Gaps >2 h | 0 (A2 PASS) |
| Daily close 00:00 UTC | 5 marcas; última ancla `2026-08-14T00:00:00+00:00` |
| Integridad tear | **PROMOTE_PAPER** |
| Revenue / live | **NO-GO** · Sharpe/Calmar/MaxDD **N/A** |

Reset N10 previo: `paper_telemetry/archive/burnin-2026-08-13T2309Z/` (inventario ~960, no forma parte de esta ventana).

---

## Parche aplicado (Paso 1) — no cambia hash

1. `execute_trading_cycle` / assess_risk / health_check leen `GRID_CONFIG_FILE` vía `resolve_grid_config_file()` (ya no hardcodean `grid_config_optimized.json`).
2. Factory/sizer: `resolve_min_notional_threshold` → freeze L0 **max(piso 15, nivel 20) = 20**. Próximos BUY @ ~1886.8 → qty **0.0106**, no 0.0053.
3. Ancla desk **2026-08-15**. Día 1/30 arranca a las 00:00 UTC del 15/08.

Tests: `tests/test_l0_grid_config_file_and_sizer.py` + ancla + A8 disco.

El fill ya persistido (qty 0.0053 / notional 10) es **pre-parche**. No wipe. No es cambio de `config_hash`.

---

## Daily close T0 (Paso 2)

Al corte de firma **estamos fuera de ventana** (±30 min 00:00 UTC).  
Dry-run: `next_window_opens_at=2026-08-14T23:30:00+00:00` → cierra `2026-08-15T00:30:00+00:00`.  
**No** se escribió sample con reloj falso (evita serie fuera de orden).

Path real (beat `capture_portfolio_snapshot` o backup):

```bash
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/capture_paper_e0_daily_close.py --write
```

EOD simulado **sí** se ejecutó: A8 PASS sin race (tear lee JSON de disco + `reset_paper_telemetry()`). Identidad contable **0**.

---

## Calendario

```
T0              = 2026-08-15 00:00 UTC
cierre ventana  = 2026-09-14 00:00 UTC  (30 retornos diarios)
go_live_candidato = T0 + 31d = 2026-09-15
contingencia    = 2026-09-22 si la serie no cierra (desk-policy §6)
```

Los samples 2026-08-13 23:10Z → 2026-08-14 23:59Z son **pre-T0** (instrumentación post-N10). No entran al conteo de 30 cierres de Capa B.

---

## Gaps (no bloquean GO; owners)

| Gap | Owner | Acción |
|-----|--------|--------|
| Daily close del T0 aún no escrito | devops | ventana 23:30–00:30Z |
| Fill 10 USDT pre-parche | MM + backend-tdd | observar próximo BUY ≥ piso 15 / nivel 20 |
| Tear A3/A8 IDs ≠ policy Quant | quant | documentado; no retune |

---

## Prohibido a partir de T0

- Bajar spacing / subir sizing / cambiar símbolo o niveles (A1/N11 → reinicio).
- Wipe de `paper_telemetry`.
- Live, `FORCE_REAL_MODE`, pegar keys.
- Resetear `system_integrity` por PnL (AS-10).
- Contar el burn-in 05–13/08 (archivo) como días de ventana.

**PROMOTE_LIVE: NO.** El primer live sigue exigiendo firma dual CEO + Desk Lead (RFC-004 / ADR-007) **después** de 30 días de serie limpia.
