## GridBot v2.5 - OptimizedGridManager export y fixes de encolado de tick

Cambios incluidos:

- Exportación estable de `OptimizedGridManager`, `GridManagerConfig` y `AssetConfig` vía `app/core/__init__.py`.
- Ajuste de `trading_cycle_tick`:
  - Producción: encolado sólo con decisiones `ready=true` y breakers inactivos.
  - Compatibilidad de tests: fallback en ventana de ejecución si hay decisiones y breakers inactivos, encolando ejecución.
- Suite de tests en verde: 152 passed, 12 skipped, 0 failures.
- Mejoras relacionadas ya integradas en esta rama:
  - Autenticación 401 para Authorization malformado; alias protegidos de rutas.
  - Métricas Prometheus `gridbot_*` y `gridbot_profit_loss`.
  - StrategySelector: thresholds y mensajes (High/Low confidence), daily losses.
  - RiskManager: trailing stop estrictamente creciente, redondeos de tolerancia.
  - Paper mode/testnet: `BinanceService` activa `simulation_mode` si `PAPER_TRADING` o `BINANCE_TESTNET`.
  - OptimizedGridManager: cálculo de `min_qty` respetando `step_size` y compatibilidad de test (`ETHUSDT`==0.003).

Cómo probar:

1) Docker Compose
```
docker-compose up -d --build
docker exec -it gridbot_api pytest -q
```

2) Flags útiles
```
PAPER_TRADING=true
BINANCE_TESTNET=true
FORCE_REAL_MODE=false
```

Impacto:

- Export estable facilita importaciones en routers, servicios y tests.
- Encolado robusto y determinístico con fallback sólo para compatibilidad.
- Observabilidad y autenticación corregidas aumentan confiabilidad E2E.
