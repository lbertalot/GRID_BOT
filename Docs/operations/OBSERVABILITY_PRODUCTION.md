# Observabilidad en Producción — GridBot v2.5

## Métricas disponibles

La app expone métricas Prometheus en:

```
GET https://grid-bot-ia-eu-3ded46704cc4.herokuapp.com/metrics
```

### Métricas clave

| Métrica | Tipo | Descripción |
|---------|------|-------------|
| `http_request_duration_seconds` | Histogram | Latencia HTTP por método/ruta/status |
| `http_requests_total` | Counter | Total requests HTTP |
| `gridbot_ml_regime_used_in_cycle_total` | Counter | Ciclos que usaron predicción ML |
| `gridbot_ml_regime_fallback_total` | Counter | Ciclos con fallback estático (reason: disabled/error) |
| `gridbot_cycle_order_executed_total` | Counter | Órdenes ejecutadas por el ciclo |
| `gridbot_active_breakers_total` | Gauge | Circuit breakers activos |
| `gridbot_cycle_phase` | Gauge | Timestamp del último heartbeat por fase |
| `gridbot_portfolio_*` | Gauge | Métricas de portafolio (PnL, ROI, valor total) |

---

## Opción A: Grafana Cloud (recomendada)

1. Crear cuenta gratuita en [grafana.com](https://grafana.com/products/cloud/)
2. En Grafana Cloud, ir a **Connections → Add new connection → Prometheus**
3. Configurar un **scrape job** remoto:
   - Target URL: `https://grid-bot-ia-eu-3ded46704cc4.herokuapp.com/metrics`
   - Scrape interval: `60s`
   - Scrape timeout: `30s` (para absorber cold start)
4. Importar dashboards desde `docker/grafana/dashboards/` o crear nuevos

### Dashboard sugerido

Paneles mínimos:
- **API Health**: `rate(http_requests_total[5m])` por status code
- **Latencia P99**: `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))`
- **ML vs Fallback**: `rate(gridbot_ml_regime_used_in_cycle_total[1h])` vs `rate(gridbot_ml_regime_fallback_total[1h])`
- **Breakers**: `gridbot_active_breakers_total`
- **Órdenes ejecutadas**: `rate(gridbot_cycle_order_executed_total[1h])`

---

## Opción B: Prometheus self-hosted (VPS)

Si tienes un VPS con Prometheus instalado:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'gridbot-production'
    scrape_interval: 60s
    scrape_timeout: 30s
    scheme: https
    static_configs:
      - targets: ['grid-bot-ia-eu-3ded46704cc4.herokuapp.com']
    metrics_path: /metrics
```

Luego conectar Grafana al Prometheus local.

---

## Opción C: Prometheus en Docker (entorno local)

Ya configurado en `docker-compose.yml`:

```bash
docker compose --profile production up -d prometheus grafana
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Dashboards precargados desde `docker/grafana/dashboards/`

---

## Alertas básicas

### Recomendadas (PromQL)

```yaml
# Dyno caído (sin scrape exitoso en 5 min)
- alert: GridBotDown
  expr: up{job="gridbot-production"} == 0
  for: 5m

# Breaker activo
- alert: BreakerActive
  expr: gridbot_active_breakers_total > 0
  for: 1m

# Latencia API alta (P99 > 5s)
- alert: HighAPILatency
  expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 5
  for: 5m

# ML siempre en fallback (posible problema)
- alert: MLAlwaysFallback
  expr: rate(gridbot_ml_regime_fallback_total[1h]) > 0 and rate(gridbot_ml_regime_used_in_cycle_total[1h]) == 0
  for: 1h
```

---

## Notas

- **Cold start**: La primera petición a `/metrics` tras idle puede tardar 10-30s. El keep-alive (`APP_URL` configurada) reduce este riesgo.
- **River no disponible**: En producción, River no está instalado (`river` no está en `requirements.txt`). El ML funciona en modo fallback (RANGE). Para habilitar River, añadir `river` a `requirements.txt` y hacer deploy.
- **Métricas de Grafana (portfolio)**: Se actualizan cada 60s en un thread dedicado que no bloquea el event loop.
