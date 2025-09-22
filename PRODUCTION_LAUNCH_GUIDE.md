# 🚀 Guía de Lanzamiento a Producción - GridBot v2.5

## ⚠️ ADVERTENCIA CRÍTICA
**Este documento describe el proceso para lanzar GridBot v2.5 con DINERO REAL.**
**Asegúrate de haber completado todas las verificaciones antes de proceder.**

## 📋 Checklist Pre-Lanzamiento

### ✅ Configuración de Credenciales
- [ ] Renombrar `production.env` a `.env`
- [ ] Reemplazar `YOUR_REAL_API_KEY_HERE` con tu API key real de Binance
- [ ] Reemplazar `YOUR_REAL_SECRET_KEY_HERE` con tu secret key real de Binance
- [ ] Configurar `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` para alertas
- [ ] Verificar que las credenciales tienen permisos de trading spot
- [ ] Confirmar que la IP está en la whitelist de Binance (si aplica)

### ✅ Configuración de Capital
- [ ] Ajustar el capital inicial en el dashboard de Grafana (reemplazar 18.47 USDT)
- [ ] Verificar que el balance de USDT en Binance es suficiente
- [ ] Confirmar que no hay órdenes abiertas en Binance
- [ ] Verificar que los símbolos de trading están configurados correctamente

### ✅ Verificación de Seguridad
- [ ] Revisar límites de pérdida diaria (5% por defecto)
- [ ] Revisar límites de pérdida total (10% por defecto)
- [ ] Confirmar que los circuit breakers están configurados
- [ ] Verificar que la blacklist de símbolos está activa

## 🚀 Proceso de Lanzamiento

### Paso 1: Configuración Inicial
```bash
# 1. Configurar credenciales
cp production.env .env
# Editar .env con tus credenciales reales

# 2. Verificar configuración
cat .env | grep -E "(BINANCE_API_KEY|BINANCE_SECRET_KEY|PAPER_TRADING|FORCE_REAL_MODE)"
```

### Paso 2: Lanzamiento Controlado
```bash
# Ejecutar script de lanzamiento
./launch.sh
```

El script realizará:
- Detención de servicios actuales
- Verificación de configuración
- Inicio en modo producción
- Verificación de salud de servicios
- Monitoreo de logs en tiempo real

### Paso 3: Configuración de Monitoreo
```bash
# Configurar monitoreo y alertas
./setup-monitoring.sh
```

### Paso 4: Importar Dashboard de Grafana
1. Abrir http://localhost:3000
2. Ir a Dashboards > Import
3. Copiar y pegar contenido de `grafana-roi-dashboard.json`
4. **IMPORTANTE**: Ajustar el capital inicial (18.47 USDT) según tu capital real

## 📊 Monitoreo Post-Lanzamiento

### Métricas Críticas a Observar
- **PnL Acumulado**: `sum(gridbot_trade_pnl_usdt_total)`
- **ROI**: `(sum(gridbot_trade_pnl_usdt_total) / CAPITAL_INICIAL) * 100`
- **Win Rate**: `(sum(gridbot_trades_successful_total) / sum(gridbot_trades_executed_total)) * 100`
- **Circuit Breakers**: `sum(gridbot_circuit_breakers_active_total)`
- **Discrepancias**: `sum(gridbot_reconciliation_discrepancies_total)`

### Alertas Críticas
- **HighDailyDrawdown**: Drawdown diario > 4%
- **CircuitBreakerActivated**: Cualquier circuit breaker activado
- **ReconciliationDiscrepancyDetected**: Discrepancias con Binance
- **BotInactivity**: Sin trades por 2 horas

### URLs de Monitoreo
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
- **API Health**: http://localhost:8000/health

## 🛑 Procedimientos de Emergencia

### Detener Trading Inmediatamente
```bash
# Activar modo crítico (detiene todo el trading)
curl -X POST http://localhost:8000/breakers/activate-critical

# O detener todos los servicios
docker-compose down
```

### Verificar Estado de Cuenta
```bash
# Verificar balance actual
curl http://localhost:8000/api/portfolio/summary

# Verificar posiciones abiertas
curl http://localhost:8000/api/portfolio/positions
```

### Reconciliación Manual
```bash
# Forzar reconciliación con Binance
curl -X POST http://localhost:8000/api/reconciliation/force
```

## 📞 Contactos de Emergencia
- **Telegram**: Configurado para alertas automáticas
- **Logs**: `docker-compose logs -f api` para debugging
- **Métricas**: Grafana para análisis de rendimiento

## 🔧 Troubleshooting Común

### API no responde
```bash
docker-compose logs api
docker-compose restart api
```

### Prometheus no recolecta métricas
```bash
docker-compose logs prometheus
curl http://localhost:9090/api/v1/targets
```

### Grafana no muestra datos
```bash
docker-compose logs grafana
# Verificar conexión a Prometheus en Grafana
```

## 📈 Optimización Post-Lanzamiento

### Ajustes de Estrategia
- Monitorear win rate y ajustar parámetros
- Revisar rendimiento por símbolo
- Ajustar límites de riesgo según resultados

### Escalabilidad
- Monitorear uso de CPU y memoria
- Ajustar recursos según necesidad
- Considerar múltiples instancias para mayor volumen

---

**🎯 Objetivo**: Mantener ROI positivo con riesgo controlado
**⏰ Monitoreo**: 24/7 durante las primeras 72 horas
**🔄 Revisión**: Diaria durante la primera semana
