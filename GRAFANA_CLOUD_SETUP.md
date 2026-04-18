# Configuración de Grafana Cloud con GridBot en Heroku

Esta guía te ayudará a configurar Grafana Cloud para monitorear tu aplicación GridBot desplegada en Heroku.

## 📋 Información de tu Aplicación

- **URL de la App**: `https://grid-bot-ia-74c1755e5f04.herokuapp.com`
- **Endpoint de Métricas**: `https://grid-bot-ia-74c1755e5f04.herokuapp.com/metrics`
- **Tu Grafana Cloud**: `https://leandrobertalot.grafana.net/`

✅ **Endpoint verificado**: El endpoint `/metrics` está funcionando y es accesible públicamente.

## Paso 1: Configurar Data Source de Prometheus en Grafana Cloud

### 1.1 Acceder a Grafana Cloud

1. Ve a: **https://leandrobertalot.grafana.net/**
2. Inicia sesión con tus credenciales

### 1.2 Crear Data Source de Prometheus

1. **Navega a Data Sources**:
   - Haz clic en el ícono de **⚙️ Configuración** (Settings) en el menú lateral izquierdo
   - Selecciona **"Data sources"**

2. **Añadir Prometheus**:
   - Haz clic en **"Add data source"**
   - Busca y selecciona **"Prometheus"**

3. **Configuración**:
   - **URL**: Usa el URL que Grafana Cloud te proporciona automáticamente
     - Debería verse algo como: `https://prometheus-prod-XX-prod-us-central-0.grafana.net`
     - **NO** uses la URL de tu app de Heroku aquí
   - **Access**: Deja **"Server (default)"** seleccionado
   - **Auth**: Deja las opciones por defecto (sin autenticación adicional)

4. **Guardar**:
   - Desplázate hacia abajo
   - Haz clic en **"Save & test"**
   - Deberías ver: ✅ **"Data source is working"**

## Paso 2: Configurar Metrics Endpoint Integration (Recomendado)

Grafana Cloud tiene una integración específica para scrapear endpoints HTTP externos. Es la forma más simple de conectar tu app.

### 2.1 Acceder a la Integración

1. **Ve a Connections**:
   - Menú lateral → **"Connections"** (o **"Integrations"**)
   - Busca y haz clic en **"Metrics Endpoint"**
   - Si no lo ves, busca en **"Browse all integrations"** y filtra por "Metrics Endpoint"

### 2.2 Configurar el Scrape Job

1. **Añade un nuevo scrape job**:
   - Haz clic en **"Add integration"** o **"Configure"**
   - Si ya tienes scrape jobs, haz clic en **"Add scrape job"**

2. **Completa la configuración**:
   - **Scrape Job Name**: `gridbot-heroku-production`
   - **Scrape Job URL**: `https://grid-bot-ia-74c1755e5f04.herokuapp.com/metrics`
   - **Scrape Interval**: `30s` o `60s` (recomendado: 60s para reducir carga)
   - **Type of Authentication Credentials**: Selecciona **"None"** (tu endpoint es público)
   - **Metrics Path**: Deja vacío (el path ya está en la URL)

3. **Probar la conexión**:
   - Haz clic en **"Test Connection"**
   - Deberías ver un ✅ mensaje de éxito
   - Si hay error, verifica que el endpoint sea accesible públicamente

4. **Guardar**:
   - Haz clic en **"Save Scrape Job"**
   - Grafana Cloud comenzará a scrapear automáticamente cada 30-60 segundos

### 2.3 Verificar que está funcionando

Después de unos minutos:
1. Ve a **"Explore"** en Grafana
2. Selecciona tu data source de Prometheus
3. Ejecuta la query: `up{job="gridbot-heroku-production"}`
4. Deberías ver un valor `1` si el scrape está funcionando

## Alternativa: Prometheus Remote Write

Si prefieres usar Remote Write (la app envía métricas a Grafana Cloud):

1. **Obtén credenciales**:
   - Ve a **"Connections"** → **"Prometheus"** → **"Send metrics"**
   - Copia:
     - **Remote Write URL**
     - **Username** (ID numérico)
     - **Password** (API Key)

2. **Configurar en tu app** (requiere código adicional)

## Paso 3: Verificar que las Métricas Llegan

1. **Usa el Explorer**:
   - Menú lateral → **"Explore"** (ícono de brújula)
   - Selecciona tu data source de Prometheus
   - En el campo de query, escribe: `gridbot_api_requests_total`
   - Haz clic en **"Run query"**
   - Deberías ver métricas apareciendo

2. **Prueba otras métricas**:
   ```
   gridbot_orders_total
   gridbot_profit_loss
   gridbot_balances_usdt
   breaker_state
   ```

## Paso 4: Importar Dashboards

### 4.1 Importar Dashboard desde JSON

1. **Ve a Dashboards**:
   - Menú lateral → **"Dashboards"** → **"Import"**

2. **Importar dashboard**:
   - Haz clic en **"Upload JSON file"** o pega el JSON directamente
   - Selecciona el archivo desde `docker/grafana/dashboards/`:
     - `gridbot-overview.json`
     - `gridbot-trading-dashboard.json`
     - `trading-profitability-dashboard.json`

3. **Configurar el dashboard**:
   - Selecciona tu data source de Prometheus
   - Haz clic en **"Import"**

### 4.2 Crear Dashboard Manual

Si prefieres crear tu propio dashboard:

1. **Nuevo Dashboard**:
   - **"Dashboards"** → **"New"** → **"New dashboard"**

2. **Añadir Panel**:
   - Haz clic en **"Add visualization"**
   - Selecciona tu data source de Prometheus
   - Ejemplo de query: `rate(gridbot_api_requests_total[5m])`

## Paso 5: Métricas Disponibles

Tu aplicación expone las siguientes métricas principales:

### Métricas de Trading
- `gridbot_orders_total` - Total de órdenes procesadas
- `gridbot_volume_total` - Volumen total negociado en USDT
- `gridbot_profit_loss` - Profit/Loss total acumulado
- `gridbot_balances_usdt` - Balances en USDT por asset

### Métricas de API
- `gridbot_api_requests_total` - Total de requests HTTP
- `gridbot_api_request_duration_seconds` - Latencia de requests (histograma)

### Métricas de Sistema
- `breaker_state` - Estado de circuit breakers (gauge, 1=activo, 0=inactivo)
- `active_breakers_total` - Número total de breakers activos

### Métricas del Sistema Operativo
- `process_cpu_seconds_total` - CPU usado
- `process_resident_memory_bytes` - Memoria RAM usada
- `python_gc_collections_total` - Garbage collections

## Paso 6: Crear Alertas (Opcional)

1. **Ve a Alerting**:
   - Menú lateral → **"Alerting"** → **"Alert rules"** → **"New alert rule"**

2. **Configurar alerta**:
   - **Name**: `GridBot High Error Rate`
   - **Query**: `rate(gridbot_api_requests_total{status_code=~"5.."}[5m]) > 0.1`
   - **Condition**: `WHEN last() OF query(A, 5m, now) IS ABOVE 0.1`

3. **Configurar notificaciones**:
   - Añade un canal de notificación (Email, Slack, Telegram, etc.)

## 🔍 Verificación y Troubleshooting

### Verificar que el endpoint funciona:
```bash
curl https://grid-bot-ia-74c1755e5f04.herokuapp.com/metrics | head -20
```

Deberías ver métricas en formato Prometheus:
```
# HELP gridbot_profit_loss PnL agregado de GridBot en USDT
# TYPE gridbot_profit_loss gauge
gridbot_profit_loss 0.0
```

### Si las métricas no aparecen en Grafana:

1. **Verifica el Data Source**:
   - Ve a Configuration → Data Sources → Prometheus
   - Haz clic en **"Save & test"** de nuevo

2. **Verifica que Grafana Cloud puede acceder a tu endpoint**:
   - El endpoint debe ser accesible públicamente (sin autenticación)
   - Prueba desde tu navegador: `https://grid-bot-ia-74c1755e5f04.herokuapp.com/metrics`

3. **Revisa los logs de Heroku**:
   ```bash
   heroku logs --tail --app grid-bot-ia | grep metrics
   ```

4. **Verifica que el scrape job está configurado**:
   - Si usas Grafana Agent, verifica que el job está activo
   - Si usas Remote Write, verifica que está enviando métricas

### Si los dashboards no muestran datos:

1. **Ajusta los nombres de las métricas**:
   - Usa el Explorer para ver qué métricas están disponibles
   - Los dashboards pueden necesitar actualizarse si los nombres de las métricas cambiaron

2. **Verifica el rango de tiempo**:
   - Asegúrate de que el dashboard está mirando el rango correcto (últimas 6 horas, 24 horas, etc.)

## 📚 Recursos Adicionales

- [Documentación de Grafana Cloud](https://grafana.com/docs/grafana-cloud/)
- [Guía de Prometheus Remote Write](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_write)
- [Métricas de GridBot](docs/08-metrics-catalog.md) (si existe en tu proyecto)

## 🎯 Próximos Pasos

Una vez configurado, puedes:
- ✅ Crear alertas personalizadas
- ✅ Configurar notificaciones por Telegram/Email
- ✅ Crear dashboards personalizados para métricas específicas
- ✅ Configurar retención de datos según tu plan
- ✅ Exportar dashboards como JSON para versionamiento

## 📞 Soporte

Si tienes problemas:
1. Revisa los logs de Heroku: `heroku logs --tail --app grid-bot-ia`
2. Verifica el endpoint: `curl https://grid-bot-ia-74c1755e5f04.herokuapp.com/metrics`
3. Consulta la documentación de Grafana Cloud

## 📝 Resumen Rápido

Para configurar Grafana Cloud rápidamente:

1. **Ve a tu Grafana Cloud**: https://leandrobertalot.grafana.net/
2. **Connections** → **Metrics Endpoint** → **Add integration**
3. **Configura**:
   - URL: https://grid-bot-ia-74c1755e5f04.herokuapp.com/metrics
   - Interval: 60s
   - Auth: None
4. **Save** y espera 1-2 minutos
5. **Explore** → Query: gridbot_api_requests_total

¡Listo! Las métricas deberían aparecer automáticamente.

