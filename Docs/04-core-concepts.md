## Conceptos Clave

### Estrategia Grid Trading
La estrategia despliega órdenes de compra/venta a distintos niveles de precio, capturando micro-movimientos del mercado. En v2.5, los parámetros del grid se adaptan al régimen (ML) y a la volatilidad (ATR), y el tamaño se calcula con Kelly fraccional bajo límites conservadores.

### Rebalanceo Automático de Portafolio (Auto-Rebalancer V2)
Cuando la liquidez en USDT cae por debajo de un umbral, el sistema liquida activos según una prioridad configurada (p.ej., SPK → HOME → SIGN → BNB → BTC) para restaurar liquidez. Todas las operaciones respetan filtros de Binance y validaciones de precisión.

### Circuit Breakers
Mecanismo de seguridad que detiene o limita el trading si se cumplen condiciones de riesgo (pérdidas diarias/absolutas, discrepancias financieras, fallos de conectividad o autenticación). Expuestos vía `GET /breakers/summary` y métricas.

### Observabilidad (Prometheus/Grafana)
El servicio expone `/metrics` con contadores, gauges e histogramas. Grafana presenta dashboards de ejecución, riesgo, finanzas y ML. Alertmanager dispara notificaciones ante condiciones anómalas (errores Binance, liquidez baja, breakers activados, discrepancias).

### Reconciliación
Proceso periódico que compara balances/posiciones internas con Binance y corrige discrepancias. Objetivo: ≤ 60 s y discrepancia ≤ 0.1%. Resultados disponibles en `GET /api/reconciliation/summary` y métricas dedicadas.


