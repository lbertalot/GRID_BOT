# Observabilidad

## Métricas Prometheus
- kelly_fraction_used{symbol}
- position_size_usdt{symbol,strategy}
- circuit_breaker_triggered{reason}
- portfolio_total_value_usdt, cash_balance_usdt
- api_rate_limit_hits_total{endpoint}
- ws_lag_ms{symbol}

## Dashboards Grafana
- Risk & Guardrails: Exposición, drawdown, breakers
- Execution Health: Latencia WS/API, rechazos, rate limits
- Financial Overview: Portfolio y Cash
- ML Performance: precisión y régimen

## Alertas (Alertmanager)
- Discrepancia financiera > 1% o > 5 USDT (5m)
- API down: warning (5m) / critical (15m)

## Buenas prácticas
- Añadir labels {symbol, strategy, phase}
- Evitar series cardinalidad alta
- Exportar métricas al inicio y en cambios de estado
