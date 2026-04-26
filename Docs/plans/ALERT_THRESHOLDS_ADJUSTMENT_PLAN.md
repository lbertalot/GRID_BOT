# Plan de Ajuste de Umbrales de Alertas - GridBot v2.5

## 🎯 Objetivo

Ajustar los umbrales de alertas de discrepancia de portafolio para eliminar falsos positivos y mantener monitoreo efectivo.

## 📊 Análisis Actual

### **Datos Reales:**
- **Balance Binance:** $359.77 USDT
- **Balance Sistema:** $355.56 USDT
- **Discrepancia Real:** $4.21 USDT (1.17%)
- **Discrepancia en Métricas:** $17.19 USDT (4.78%)

### **Problema Identificado:**
- **Umbral Actual:** $5.00 USDT (1.39% del portfolio)
- **Discrepancia Real:** $4.21 USDT (dentro del umbral)
- **Métricas Incorrectas:** Reportando $17.19 USDT (fuera del umbral)

## 🎯 Plan de Ajuste

### **Fase 1: Umbrales Dinámicos (Inmediato)**

#### **Nuevos Umbrales Basados en % del Portfolio:**

```yaml
# Umbrales Dinámicos
portfolio_size: $359.77

# Umbrales por Nivel
INFO: 1.5% = $5.40     # Solo logging, sin alertas
WARNING: 2.5% = $8.99  # Alertas de monitoreo
CRITICAL: 5.0% = $17.99 # Alertas urgentes
```

#### **Ventajas:**
- ✅ Escala automáticamente con el crecimiento del portfolio
- ✅ Elimina falsos positivos por discrepancias normales
- ✅ Mantiene sensibilidad para problemas reales

### **Fase 2: Implementación Técnica**

#### **Archivo a Modificar:**
`docker/prometheus/rules/discrepancy_rules.yml`

#### **Cambios Propuestos:**

```yaml
groups:
  - name: gridbot-discrepancy
    rules:
      # Alerta INFO (1.5% del portfolio)
      - alert: GridBotPortfolioDiscrepancyInfo
        expr: |
          balance_discrepancy_usd > (portfolio_total_value_usdt * 0.015)
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Discrepancia de portafolio >1.5%"
          description: "Diferencia entre sistema y Binance supera 1.5% del portfolio."

      # Alerta WARNING (2.5% del portfolio)
      - alert: GridBotPortfolioDiscrepancyWarning
        expr: |
          balance_discrepancy_usd > (portfolio_total_value_usdt * 0.025)
        for: 8m
        labels:
          severity: warning
        annotations:
          summary: "Discrepancia de portafolio >2.5%"
          description: "Diferencia entre sistema y Binance supera 2.5% del portfolio."

      # Alerta CRITICAL (5.0% del portfolio)
      - alert: GridBotPortfolioDiscrepancyCritical
        expr: |
          balance_discrepancy_usd > (portfolio_total_value_usdt * 0.050)
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Discrepancia de portafolio >5.0%"
          description: "Diferencia entre sistema y Binance supera 5.0% del portfolio."

      # Mantener alerta absoluta como fallback
      - alert: GridBotPortfolioDiscrepancyHighAbsolute
        expr: |
          balance_discrepancy_usd > 20
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Discrepancia de portafolio >20 USDT"
          description: "Diferencia absoluta muy alta independiente del portfolio size."
```

### **Fase 3: Configuración de Notificaciones**

#### **Configuración de Alertmanager:**

```yaml
# En docker/prometheus/alertmanager.yml
route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
  - match:
      severity: info
    receiver: 'info-alerts'
    repeat_interval: 2h
  - match:
      severity: warning
    receiver: 'warning-alerts'
    repeat_interval: 30m
  - match:
      severity: critical
    receiver: 'critical-alerts'
    repeat_interval: 5m

receivers:
- name: 'info-alerts'
  telegram_configs:
  - bot_token: '${TELEGRAM_BOT_TOKEN}'
    chat_id: '${TELEGRAM_CHAT_ID}'
    message: 'ℹ️ INFO: {{ .GroupLabels.alertname }}'

- name: 'warning-alerts'
  telegram_configs:
  - bot_token: '${TELEGRAM_BOT_TOKEN}'
    chat_id: '${TELEGRAM_CHAT_ID}'
    message: '⚠️ WARNING: {{ .GroupLabels.alertname }}'

- name: 'critical-alerts'
  telegram_configs:
  - bot_token: '${TELEGRAM_BOT_TOKEN}'
    chat_id: '${TELEGRAM_CHAT_ID}'
    message: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
```

### **Fase 4: Validación y Testing**

#### **Criterios de Validación:**

1. **Discrepancia Actual ($4.21):**
   - ✅ No debe generar alertas CRITICAL
   - ✅ Puede generar alertas INFO (opcional)
   - ❌ No debe generar alertas WARNING

2. **Discrepancia Moderada ($8.00):**
   - ✅ Debe generar alertas WARNING
   - ❌ No debe generar alertas CRITICAL

3. **Discrepancia Alta ($18.00):**
   - ✅ Debe generar alertas CRITICAL
   - ✅ Debe activar notificaciones urgentes

### **Fase 5: Monitoreo Post-Implementación**

#### **Métricas a Vigilar:**

1. **Frecuencia de Alertas:**
   - INFO: Máximo 2 por día
   - WARNING: Máximo 1 por día
   - CRITICAL: Máximo 1 por semana

2. **Precisión de Alertas:**
   - 90% de alertas deben ser válidas
   - 0% de falsos positivos por discrepancias normales

3. **Tiempo de Respuesta:**
   - INFO: 2 horas
   - WARNING: 30 minutos
   - CRITICAL: 5 minutos

## 🚀 Plan de Implementación

### **Paso 1: Backup de Configuración Actual**
```bash
cp docker/prometheus/rules/discrepancy_rules.yml docker/prometheus/rules/discrepancy_rules.yml.backup
```

### **Paso 2: Aplicar Nuevos Umbrales**
```bash
# Modificar archivo de reglas
# Reiniciar Prometheus
docker-compose restart prometheus
```

### **Paso 3: Validar Implementación**
```bash
# Verificar que las alertas actuales se resuelvan
# Monitorear por 1 hora
# Confirmar que no hay falsos positivos
```

### **Paso 4: Ajustes Finos**
```bash
# Si es necesario, ajustar umbrales basado en observación
# Documentar cambios finales
```

## 📊 Beneficios Esperados

### **Inmediatos:**
- ✅ Eliminación de falsos positivos
- ✅ Reducción de ruido en alertas
- ✅ Mejor experiencia de monitoreo

### **A Largo Plazo:**
- ✅ Escalabilidad automática con crecimiento del portfolio
- ✅ Monitoreo más inteligente y contextual
- ✅ Mejor gestión de incidentes

## 🎯 Resultados Esperados

### **Antes:**
- 🚨 Alertas cada 6 minutos por discrepancia de $4.21
- 📊 Umbral fijo de $5.00 (no escalable)
- 😤 Ruido excesivo en notificaciones

### **Después:**
- ✅ Sin alertas por discrepancias normales (< 1.5%)
- 📊 Umbrales dinámicos que escalan con el portfolio
- 🎯 Alertas solo para problemas reales

---

**Fecha de Plan:** 2025-09-21 14:45:00
**Analista:** GridBot Monitoring System
**Estado:** 📋 PLANO - Listo para implementación
