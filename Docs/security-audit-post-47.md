# Security audit A2 — post PR #47 (S-GATE / CEO Acta 02)

**Repo:** GRID_BOT (`main` post merge PR #47+)  
**Fecha:** 2026-08-05  
**Modo:** paper-first — sin live, sin secrets en este documento  
**Branch de remediación:** `chore/security-post-47`

## Resumen ejecutivo

Tras S-GATE (PR #47), el choke-point `assert_real_order_allowed` cubría bien
`create_order` en singleton / async wrapper / TradeExecutor / grid manager /
rebalancer. **Quedaban bypasses vía `order_market_*` / `order_limit_*` del
cliente python-binance**, usados por HTTP `/order`, `OrderValidator`,
`BinanceService` (path real) y estrategias DCA/Scalping.

`app/api/risk_routes.py` seguía **huérfano** (no wired en `main`) con
`POST /emergency-stop` histórico **sin auth** — riesgo de cableado accidental.

Redacción S11 de secrets en logs: **sin regresión material**.

Defaults de snapshot / `env.example`: sesgo a live por omisión corregido
(paper + `TRADING_ENABLED=false`).

## Crítica

### C1 — `order_market_*` / `order_limit_*` sin S-GATE

| Path | Archivo | Estado pre-fix |
|------|---------|------------------|
| `OrderValidator.place_market_order_with_validation` | `app/services/order_validation.py` | Sin guard → `/run_grid` + `scheduler/grid_job.py` |
| `POST /order` fallback + LIMIT | `app/api/trade.py` | Fallback directo a `Client.order_market_*` / `order_limit_*` |
| `BinanceService.execute_trading_order` | `app/services/binance_service.py` | Paper simula; con `FORCE_REAL_MODE` iba a exchange sin gate |
| Scalping / DCA `_place_*_order` | `app/strategies/*.py` | `singleton.client.order_market_*` (raw Client) |

**Remediación (aplicada):** `assert_real_order_allowed` en cada path; HTTP mapea `RealOrderBlocked` → 403.

## Alta

### A1 — `risk_routes.py` huérfano sin auth

No registrado en main. Remediación: **410 Gone** + `require_auth` (defense-in-depth).

### A2 — Defaults fail-closed

`get_trading_mode_snapshot`: `PAPER_TRADING` default `true`, `TRADING_ENABLED` default `false`.
`env.example`: `TRADING_ENABLED=false`.

## Media

- Compose: `TRADING_ENABLED=${TRADING_ENABLED:-false}` (follow-up).
- Unificar ejecución vía TradeExecutor.
- Inventariar `optimized_routes` emergency huérfano.

## Baja

- S11 redacción secrets: sin regresión.
- `binance_user_stream` apiKey en query de firma (no log).

## Artefactos

- Informe: este archivo
- Fix + tests: branch `chore/security-post-47`
