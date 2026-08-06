# Desk hourly status → Telegram (ventana paper L0)

**Modo:** paper-only · **No** autoriza live  
**Habilitado local:** `DESK_HOURLY_STATUS_ENABLED=true` (compose local)

## Qué hace
Cada hora (**minuto :05 UTC**) Celery Beat dispara `send_desk_hourly_digest` con un
mensaje CEO compacto:

```
🧭 Reporte CEO | Día N/30 (HH:MMZ)
⚙️ Modo: Paper Trading | Pase a Live: ❌ NO
💵 Resumen de Capital: Equity + Variación vs E_0
⚠️/✅ Alerta global + acción si AT_RISK/OFF_TRACK
✅ Áreas ON TRACK resumidas + notas técnicas (samples / cierres)
```

Sin claim de edge; **Pase a Live siempre ❌ NO** en este canal.

A las **00:45 UTC** `send_desk_eod_day_plan` escribe:
`Docs/ops/day{N+1}-action-plan-YYYY-MM-DD.md` y un resumen corto por Telegram.

## Fuentes
- `/` trading mode (`effective_mode`)
- `paper_telemetry/paper_equity_series.json`
- `GRID_CONFIG_HASH` (freeze)
- Breakers (`get_breakers_status`)

## Manual
```bash
# Dry-run (imprime payload)
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/send_desk_hourly_status.py --dry-run

# Enviar ahora
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/send_desk_hourly_status.py

# Action plan Día N+1
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/send_desk_hourly_status.py --eod
```

Requiere `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` en `.env`.

## Ancla ventana
`DESK_WINDOW_DAY0_ANCHOR=2026-08-06` → día 1/30 el 2026-08-06 UTC.
