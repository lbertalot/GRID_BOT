# Desk hourly status → Telegram (ventana paper L0)

**Modo:** paper-only · **No** autoriza live  
**Habilitado local:** `DESK_HOURLY_STATUS_ENABLED=true` (compose local)

## Qué hace
Cada hora (**minuto :05 UTC**) Celery Beat dispara `send_desk_hourly_digest`.
Al CEO (default `TELEGRAM_CEO_PLAIN=true`) llega el copy llano — ver
[`TELEGRAM_CEO_PLAIN.md`](TELEGRAM_CEO_PLAIN.md). No se reenvía si el semáforo
no cambió. Las ACCIONES de área **no** van a Telegram CEO (sí al day-plan / log).

Formato desk (`TELEGRAM_CEO_PLAIN=false`):

```
🧭 Reporte CEO | Día N/30 (HH:MMZ)
⚙️ Modo: Paper Trading | Pase a Live: ❌ NO
...
```

Sin claim de edge; **Dinero real: NO** / Pase a Live ❌ NO.

A las **00:45 UTC** `send_desk_eod_day_plan` escribe:
1. Tear Capa A auto → `Docs/ops/tear-capa-a-YYYY-MM-DD.md` (`app/core/desk_tear_capa_a.py`, AS-1)
2. `Docs/ops/day{N+1}-action-plan-YYYY-MM-DD.md`
3. Resumen corto por Telegram (incluye path del tear · **PROMOTE_LIVE: NO**)

## Acciones por área (AS-2)

Tras auto-remediate y al construir el digest, si hay áreas **AT_RISK** / **OFF_TRACK**:
`plan_actions_for_areas` queda en log / day-plan. Telegram `🛠️ DESK AUTO · ACCIONES`
solo con `TELEGRAM_DESK_VERBOSE=true`. No requiere paste del CEO.

**Umbral PnL (CEO 2026-08-10):** Δ equity vs E_0 (`E0_REFERENCE=1000`):
- ≤ **−1.5%** → MM + QUANT **AT_RISK** (global ≥ AT_RISK) + ACCIONES
- ≤ **−3.0%** → MM + QUANT **OFF_TRACK**
- ≤ **−5.0%** → **PAUSE_GATE** MM/QUANT/RISK OFF + ACCIONES
  `desk-lead: evaluar EMERGENCY_STOP paper` (**no** auto-flip; PROMOTE_LIVE NO)
  (token `PAUSE_GATE` solo cuando dispara; legend usa `gate_pausa=` para no FP)
Override opcional: `DESK_EQUITY_DD_AT_RISK_PCT` / `DESK_EQUITY_DD_OFF_TRACK_PCT` /
`DESK_EQUITY_DD_PAUSE_PCT`.

Código: `app/core/desk_area_actions.py` · umbral en `desk_hourly_status.py`.

## Auto-remediación (sin paste Telegram)

Antes del digest / EOD plan, si `DESK_AUTO_REMEDIATE_BREAKERS=true` (default):

1. Modo paper SoT
2. `system_integrity` abierto
3. Binance `auth_ok` + `net_ok`
4. **Reason allowlist** solo: `binance_net_fail` / `binance_auth_fail` (y aliases)

→ **reset paper-safe** del breaker + Telegram `🛠️ DESK AUTO · REMEDIADO`.

Si validate falla → Telegram `🛠️ DESK AUTO · HOLD` (revisar IP allowlist).
Skill: `trading-binance-ip-allowlist` · runbook: `Docs/engineering/runbook-binance-ip-allowlist-browser.md`.  
Si reason es trading/PnL (p.ej. *pérdidas consecutivas*, IC-2) → **no** reset.
Telegram CEO: recordatorio **cada 6 h** mientras SI siga abierto (`breaker_ceo_watch`);
al cerrar SI → aviso inmediato “freno levantado”.
Owner: RISK+MM + firma Desk Lead para override.
Kill switch: `DESK_AUTO_REMEDIATE_BREAKERS=false`.

El digest se construye **después** del intento, para reflejar RISK ON_TRACK si el reset funcionó.

Código: `app/core/desk_auto_remediation.py` · cableado en `app/services/desk_status_tasks.py`.

## Fuentes
- `/` trading mode (`effective_mode`)
- `paper_telemetry/paper_equity_series.json`
- `GRID_CONFIG_HASH` (freeze)
- Breakers (`get_breakers_status`)

## Manual
```bash
# Dry-run (imprime payload; no remedia ni Telegram)
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/send_desk_hourly_status.py --dry-run

# Enviar ahora (incluye auto-remediate)
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/send_desk_hourly_status.py

# Action plan Día N+1
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/send_desk_hourly_status.py --eod
```

Requiere `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` en `.env`.

## Ancla ventana
`DESK_WINDOW_DAY0_ANCHOR=2026-08-15` → día 1/30 el 2026-08-15 UTC (T0 canónico post-reset N10).

