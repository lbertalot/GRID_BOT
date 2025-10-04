## Mapa de Endpoints → Código

| Endpoint | Archivo | Función |
|---|---|---|
| GET /health | app/main.py | health |
| GET /metrics | app/api/prometheus.py | router (exposición) |
| POST /api/metrics/update-pnl (auth) | app/api/metrics.py | update_pnl_metrics |
| GET /trade/trades (auth) | app/api/trade.py | get_trades |
| GET /trade/grid_config (auth) | app/api/trade.py | get_grid_config_endpoint |
| GET /breakers/summary | app/main.py | breakers_summary |
| GET /api/reconciliation/summary | app/main.py | reconciliation_summary |
| POST /api/simulations/dry-run | app/api/simulations.py | router (dry-run) |
| GET /api/portfolio/summary | app/api/portfolio_routes.py | router |
| GET /api/portfolio/positions | app/api/portfolio_routes.py | get_portfolio_positions |

Para contratos completos, ver `docs/openapi.json`.


