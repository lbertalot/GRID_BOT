# Simulacro IC desk A5 — 2026-08-10

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-10T12:52:57.928972+00:00 |
| Modo | paper · **PROMOTE_LIVE: NO** |
| Script | `scripts/simulacro_ic_a5_paper.py` |
| Aislamiento | tmp ledger · **no** muta `paper_telemetry/` prod |
| Veredicto | **PASS** |

## 1. IC-1 — mid bajo piso (−5%)

| Check | Resultado |
|-------|-----------|
| `ic1_active` | True |
| `allows_core_buy` | False |
| pending BUY after cancel | 0 |
| cancel_buys event | True |
| Pass | **True** |

## 2. IC-2 — DD ≥ 10% desplegado + flatten

| Check | Resultado |
|-------|-----------|
| peak → equity | 999.76924 → 979.76924 |
| mark forzado | 1723.0000 |
| `ic2_active` / armed | True / False |
| fills flatten | 1 |
| open qty after flatten | 0 |
| breaker trips | [('system_integrity', 'IC2_flatten_core_at_deployed_dd')] |
| Pass | **True** |

## Go / no-go
- Simulacro A5 código: **PASS**
- Gate live: **NO-GO** · **PROMOTE_LIVE: NO**
- KPI SELL / ventana: ver `IC_SELL_STATUS_*.md` (evidencia separada)

```json
{
  "at": "2026-08-10T12:52:57.928972+00:00",
  "mode": "paper",
  "promote_live": "NO",
  "steps": {
    "ic1_force_below_floor": {
      "ic1_active": true,
      "allows_core_buy": false,
      "pending_buys_after": 0,
      "events": [
        "IC1_stop_rebuy_outside_range"
      ],
      "cancel_buys_event": true,
      "pass": true
    },
    "ic2_force_dd_flatten": {
      "peak_equity": "999.76924",
      "equity_after": "979.76924",
      "mark": "1723.0000",
      "ic2_active": true,
      "ic2_should_flatten": true,
      "flatten_pending_after": false,
      "armed": false,
      "fills_n": 1,
      "open_qty_after": "0",
      "breaker_trips": [
        [
          "system_integrity",
          "IC2_flatten_core_at_deployed_dd"
        ]
      ],
      "allows_core_buy": false,
      "events_ic2": true,
      "pass": true
    }
  },
  "verdict": "PASS",
  "events_seen": [
    "IC1_stop_rebuy_outside_range",
    "IC2_flatten_core_at_deployed_dd"
  ]
}
```
