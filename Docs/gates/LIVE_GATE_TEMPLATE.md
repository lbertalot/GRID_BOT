# LIVE GATE — PLANTILLA (NO FIRMADA)

Artefacto de gate live según `Docs/engineering/ADR-007-live-gate-dual-signoff.md`
y `Docs/product/rfc/RFC-004-golive-dashboard-gate.md` del monorepo.
Regla dura: `.cursor/rules/40-no-live-without-gate.mdc`.

**Esta plantilla nunca habilita live.** `app/core/live_gate.py` rechaza cualquier
archivo cuyo nombre contenga `TEMPLATE`, y los placeholders `<...>` no cuentan
como firma.

## Cómo se usa

1. Copiar a `Docs/gates/LIVE_GATE_<YYYYMMDD>.md` **fuera de git** (los gates
   firmados están en `.gitignore`: son artefactos de operación, no de código).
2. Guardarlo en el host de deploy con permisos restringidos: `chmod 600`.
   Un archivo world-writable se rechaza (`gate_file_insecure_permissions`).
3. Marcar todos los items del checklist con `[x]`. Uno sin marcar → no firmado.
4. Completar **las dos** firmas con nombre real y timestamp ISO-8601.
   Una sola firma no arma live.
5. Apuntar el runtime con `LIVE_GATE_PATH=/ruta/LIVE_GATE_<YYYYMMDD>.md`
   (o `LIVE_GATE_DIR=/ruta/gates`, default `Docs/gates`).
6. Verificar con `GET /api/gates/live-status` antes de tocar cualquier flag.

El gate es condición **necesaria y no suficiente**: `EMERGENCY_STOP`,
`TRADING_ENABLED` y los circuit breakers siguen mandando.

## Checklist

- [ ] Dashboard en verde (`effective_mode`, equity, DD% vs aportado, PnL MTD)
- [ ] Risk engine con límites de capital y kill floor verificados
- [ ] Mode clarity expuesto y correcto en `/health/trading-mode`
- [ ] Tear sheet paper ≥ 3 semanas con expectancy semanal ≥ 0 tras fees
- [ ] Sin breach de reglas de riesgo en paper
- [ ] Secrets fuera de git; keys solo en secret manager / env runtime
- [ ] Keys de exchange sin permiso de withdraw
- [ ] `EMERGENCY_STOP` probado end-to-end
- [ ] Observabilidad operativa (métricas, alertas, logs)
- [ ] Rollback plan escrito y probado
- [ ] Reconciliación contra exchange en verde

## Config

- config_hash: `<sha256 de grid config + env flags NO secretos>`

## Signoffs

Formato exacto que parsea el módulo (`signer` y `timestamp` entre comillas):

- ceo_signoff: signer="<NOMBRE CEO>" timestamp="<YYYY-MM-DDTHH:MM:SS-03:00>"
- desk_lead_signoff: signer="<NOMBRE DESK LEAD>" timestamp="<YYYY-MM-DDTHH:MM:SS-03:00>"

## Confirmación humana

Además del artefacto, la regla `40-no-live-without-gate` exige confirmación
escrita del humano: "autorizo live en \<exchange\> con capital \<X\>".
Este archivo no la reemplaza.
