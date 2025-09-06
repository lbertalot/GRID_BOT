# GridBot V2.5 - "Low-Risk, Predictive & Adaptive Grid"

## 🚀 Resumen Ejecutivo

GridBot V2.5 representa una evolución significativa del sistema de trading automatizado, introduciendo capacidades predictivas y adaptativas avanzadas. Esta versión implementa un enfoque de gestión de riesgos sofisticado con Kelly fraccional, predicción de régimen de mercado mediante machine learning híbrido, y selección automática de estrategias.

## 🎯 Características Principales

### 🔒 Gestión de Riesgos Evolucionada
- **Kelly Fraccional**: Cálculo dinámico de tamaño de posición basado en winrate y ratio ganancia/pérdida
- **Trailing Stops Adaptativos**: Stops dinámicos basados en ATR (Average True Range)
- **Circuit Breaker**: Sistema de protección automática con múltiples niveles
- **Filtros de Régimen**: Ajuste automático de exposición según condiciones de mercado

### 🤖 Machine Learning Híbrido
- **Modelos Deep Learning**: LSTM y Transformer para predicción de régimen a largo plazo
- **River ML**: Aprendizaje online para predicción a corto plazo
- **Predicción de Régimen**: Identificación automática de condiciones de mercado (BULL, BEAR, RANGE, HIGH_VOL)

### 🎯 Selección Automática de Estrategias
- **StrategySelector**: Selección inteligente basada en predicciones y estado de cuenta
- **Estrategias Adaptativas**: Grid Trading, DCA, Scalping, Hedging según condiciones
- **Parámetros Dinámicos**: Ajuste automático de parámetros según volatilidad y riesgo

### 📊 Backtesting Avanzado
- **vectorbt**: Simulación de alta precisión con comisiones y slippage
- **Walk-Forward Analysis**: Validación robusta con ventanas deslizantes
- **Métricas Completas**: Sharpe, Sortino, Max Drawdown, Win Rate

### 🔗 Cliente Binance Mejorado
- **Validación de Filtros**: Prevención de errores API con validación completa
- **Rate Limiting**: Token bucket con backoff exponencial y jitter
- **WebSocket**: Conexiones en tiempo real con fallback automático
- **Métricas**: Monitoreo completo de latencia y errores

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   HybridMLEngine│    │ StrategySelector│    │  RiskManager    │
│                 │    │                 │    │                 │
│ • LSTM/Transformer│  │ • Regime Analysis│   │ • Kelly Fractional│
│ • River ML      │    │ • Strategy Logic │   │ • Trailing Stops │
│ • Regime Predict│    │ • Dynamic Params │   │ • Circuit Breaker│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ BacktestingService│
                    │                 │
                    │ • vectorbt      │
                    │ • Walk-Forward  │
                    │ • Performance   │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │ BinanceClient   │
                    │                 │
                    │ • Validation    │
                    │ • Rate Limiting │
                    │ • WebSocket     │
                    └─────────────────┘
```

## 📁 Estructura de Archivos

```
app/
├── core/
│   └── risk_manager.py          # RiskManager evolucionado
├── exchanges/
│   ├── __init__.py
│   ├── exceptions.py            # Excepciones personalizadas
│   └── binance_client.py        # Cliente Binance mejorado
├── services/
│   ├── hybrid_ml_engine.py      # Motor ML híbrido
│   ├── strategy_selector.py     # Selector de estrategias
│   └── backtesting_service.py   # Servicio de backtesting
└── api/
    ├── risk_routes.py           # Endpoints de riesgo
    └── strategy_routes.py       # Endpoints de estrategias

tests/
├── test_risk_manager_v2.py      # Tests del RiskManager
└── test_strategy_selector.py    # Tests del StrategySelector

scripts/
└── test_v25_implementation.py   # Script de pruebas completo
```

## 🚀 Instalación y Configuración

### Requisitos del Sistema
```bash
Python 3.11+
PostgreSQL 13+
Redis 6+
Docker & Docker Compose
```

### Dependencias Principales
```bash
pip install -r requirements.txt
```

Dependencias clave:
- `fastapi>=0.104.0`
- `pydantic>=2.0.0`
- `tensorflow>=2.13.0`
- `river>=0.20.0`
- `vectorbt>=0.25.0`
- `prometheus-client>=0.17.0`
- `aiohttp>=3.8.0`
- `websockets>=11.0.0`

### Configuración del Entorno
```bash
# Copiar archivo de configuración
cp env.example .env

# Configurar variables de entorno
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_TESTNET=true
DATABASE_URL=postgresql://user:pass@localhost/gridbot
REDIS_URL=redis://localhost:6379
```

## 🧪 Ejecución de Pruebas

### Tests Unitarios
```bash
# Ejecutar todos los tests
pytest tests/ -v

# Tests específicos
pytest tests/test_risk_manager_v2.py -v
pytest tests/test_strategy_selector.py -v
```

### Script de Pruebas Completo
```bash
# Ejecutar script de verificación V2.5
python scripts/test_v25_implementation.py
```

### Cobertura de Tests
```bash
pytest --cov=app tests/ --cov-report=html
```

## 📊 API Endpoints

### Risk Management (v2)
```bash
# Estado de riesgo
GET /api/v2/risk/status

# Activar stop de emergencia
POST /api/v2/risk/emergency-stop
Body: {"reason": "string"}

# Calcular tamaño de posición
POST /api/v2/risk/calculate-position-size
Body: {
  "symbol": "BTCUSDT",
  "account_equity": 10000.0,
  "atr": 0.02,
  "winrate_estimate": 0.6,
  "avg_win_loss_ratio": 1.5,
  "price": 50000.0
}

# Trailing stop adaptativo
POST /api/v2/risk/calculate-trailing-stop
Body: {
  "symbol": "BTCUSDT",
  "entry_price": 50000.0,
  "atr": 1000.0,
  "multiplier_atr": 2.0,
  "is_long": true
}
```

### Estrategias Inteligentes (v2)
```bash
# Ejecutar estrategia inteligente
POST /api/v2/strategies/execute_intelligent
Body: {
  "symbol": "BTCUSDT",
  "account_state": {...},
  "paper_mode": true,
  "quick_backtest": true
}

# Última decisión de estrategia
GET /api/v2/strategies/last_decision?symbol=BTCUSDT

# Ejecutar backtest
POST /api/v2/strategies/backtest/run
Body: {
  "symbol": "BTCUSDT",
  "strategy_spec": {...},
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-31T23:59:59Z",
  "initial_capital": 10000.0,
  "walk_forward": true
}

# Estado de modelos ML
GET /api/v2/strategies/ml/status?symbol=BTCUSDT
```

## 🔧 Configuración Avanzada

### RiskManager
```python
from app.core.risk_manager import RiskManager

# Configuración personalizada
risk_manager = RiskManager()
risk_manager.fractional_kelly = 0.25  # 25% de Kelly
risk_manager.min_kelly_confidence = 0.6
risk_manager.default_multiplier_atr = 2.0
```

### HybridMLEngine
```python
from app.services.hybrid_ml_engine import HybridMLEngine, DeepModelConfig

# Configuración de modelo deep learning
config = DeepModelConfig(
    model_type="LSTM",
    sequence_length=60,
    hidden_units=128,
    epochs=100
)

ml_engine = HybridMLEngine()
await ml_engine.train_deep_model(df, "BTCUSDT", config=config)
```

### StrategySelector
```python
from app.services.strategy_selector import StrategySelector

# Configuración de estrategias
selector = StrategySelector(risk_manager)

# Selección automática
strategy_spec = selector.select_strategy(
    regime_prediction, "BTCUSDT", account_state
)
```

## 📈 Métricas y Monitoreo

### Métricas Prometheus
```yaml
# Métricas de riesgo
kelly_fraction_used{symbol="BTCUSDT"}
position_size_usdt{symbol="BTCUSDT", strategy="dynamic"}
daily_loss_pct{symbol="BTCUSDT"}
total_exposure_pct{symbol="BTCUSDT"}
circuit_breaker_triggered{reason="daily_loss_limit"}

# Métricas de ML
regime_predictions_total{symbol="BTCUSDT", long="BULL_TREND", short="RANGE"}
regime_confidence{symbol="BTCUSDT", horizon="long"}
model_accuracy{model_type="deep", symbol="BTCUSDT"}

# Métricas de ejecución
orders_rejected_total{reason="price_below_min", symbol="BTCUSDT"}
api_rate_limit_hits_total{endpoint="order"}
ws_lag_ms{symbol="BTCUSDT", type="bookTicker"}
```

### Dashboards Grafana
- **Risk & Guardrails**: Exposición, drawdown, breaker state
- **Execution Health**: Latencia WebSocket, rechazos, rate limits
- **ML Performance**: Precisión de modelos, predicciones de régimen
- **Strategy Performance**: Rendimiento por estrategia y símbolo

## 🔒 Seguridad y Mejores Prácticas

### Gestión de Credenciales
```bash
# Usar secrets manager en producción
export BINANCE_API_KEY=$(aws secretsmanager get-secret-value --secret-id binance-api-key --query SecretString --output text)
export BINANCE_API_SECRET=$(aws secretsmanager get-secret-value --secret-id binance-api-secret --query SecretString --output text)
```

### Validación de Entrada
- Todos los endpoints validan entrada con Pydantic
- Validación de filtros de Binance antes de enviar órdenes
- Rate limiting automático para prevenir abuso

### Logging y Auditoría
```python
import logging

# Configuración de logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 🚀 Deployment

### Docker Compose
```yaml
version: '3.8'
services:
  gridbot:
    build: .
    environment:
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - prometheus
      - grafana

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: gridbot
      POSTGRES_USER: gridbot
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:6-alpine

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gridbot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gridbot
  template:
    metadata:
      labels:
        app: gridbot
    spec:
      containers:
      - name: gridbot
        image: gridbot:latest
        ports:
        - containerPort: 8000
        env:
        - name: BINANCE_API_KEY
          valueFrom:
            secretKeyRef:
              name: binance-secrets
              key: api-key
```

## 📚 Documentación Adicional

### Guías de Usuario
- [Guía de Deployment](Docs/DEPLOYMENT_GUIDE.md)
- [Configuración de Binance](Docs/BINANCE_SETUP_GUIDE.md)
- [Monitoreo y Alertas](Docs/MONITORING_GUIDE.md)

### Documentación Técnica
- [Verificación de Tests](Docs/VERIFICACION_TESTS_FINAL.md)
- [Resumen de Actualizaciones](Docs/RESUMEN_FINAL_ACTUALIZACION.md)
- [Comandos Rápidos](Docs/QUICK_COMMANDS.md)

### Índice de Documentación
- [Índice Completo](Docs/INDEX_DOCUMENTACION.md)

## 🤝 Contribución

### Estándares de Código
- Python 3.11+ con type hints
- Pydantic para validación de datos
- Tests unitarios con pytest
- Documentación con docstrings

### Proceso de Desarrollo
1. Fork del repositorio
2. Crear feature branch
3. Implementar cambios con tests
4. Ejecutar script de pruebas V2.5
5. Crear Pull Request

### Checklist de PR
- [ ] Tests unitarios > 85% cobertura
- [ ] Tests de integración pasando
- [ ] Documentación actualizada
- [ ] Métricas Prometheus agregadas
- [ ] Validación de entrada implementada

## 📞 Soporte

### Canales de Soporte
- **Issues**: GitHub Issues para bugs y feature requests
- **Discussions**: GitHub Discussions para preguntas generales
- **Documentación**: Wiki del proyecto para guías detalladas

### Contacto
- **Email**: support@gridbot.com
- **Telegram**: @gridbot_support
- **Discord**: GridBot Community

---

## 🎉 Conclusión

GridBot V2.5 representa un salto significativo en la automatización de trading, combinando gestión de riesgos sofisticada con machine learning predictivo y selección automática de estrategias. El sistema está diseñado para ser robusto, escalable y fácil de mantener, proporcionando una base sólida para el trading automatizado de alta frecuencia.

**¡Bienvenido al futuro del trading automatizado! 🚀**

## 📁 Artefactos y Directorios de Salida

A partir de v2.5, los artefactos JSON se consolidan y parametrizan vía variables de entorno:

- MONITORING_DIR (por defecto: `monitoring_data/`)
  - `monitoring_summary_*.json`
  - `continuous_72h_monitoring_data_*.json`
  - `intensive_monitoring_report_*.json`
  - `extended_monitoring_report_*.json`

- REPORTS_DIR (por defecto: `reports/`)
  - `audits/`: `complete_system_audit_report.json`, `reporte_analisis_problemas.json`
  - `incidents/`: `emergency_stop_report.json`
  - `safety/`: `real_trading_safety_validation.json`
  - `stabilization/`: `massive_stabilization_report.json`
  - `performance/`: `performance_evaluation_report_*.json`
  - `integrity/`: `integrity_system_test_report_*.json`, `integrity_components_test_report_*.json`
  - `phase8/`: `phase8_2_ethusdt_report.json`, `phase8_3_bnbusdt_report.json`
  - `plans/`: `phase8_activation_plan.json`, `monitoring_plan_*.json`, `final_action_plan_*.json`, `gradual_activation_plan_*.json`, `reactivation_plan_*.json`, `stabilization_plan_*.json`, `real_trading_activation_plan_*.json`

En raíz solo permanecen JSON requeridos en runtime:
- `grid_config_minimal.json`, `grid_config_optimized.json`, `grid_config_safe.json`
- `circuit_breaker_state.json`, `precision_cache.json`, `monitoring_data.json`, `continuous_monitoring.json`, `paper_trading_state.json`

Notas:
- `.gitignore` ignora `monitoring_data/**` y `reports/**` (se mantienen con `.gitkeep`).
- `docker-compose.yml` monta `./monitoring_data -> /app/monitoring_data` y `./reports -> /app/reports` y exporta `MONITORING_DIR`/`REPORTS_DIR`.
- Configura en `.env` según necesidad, o usa los defaults del `env.example`.

### 📂 Detalle de subcarpetas y formatos

- MONITORING_DIR (`monitoring_data/`):
  - `monitoring_summary_YYYYMMDD_HHMMSS.json`: snapshot horario con score, readiness y alertas.
  - `continuous_72h_monitoring_data_YYYYMMDD.json`: sesión de 72h con lista de checks.
  - `intensive_monitoring_report_YYYYMMDD_HHMMSS.json`: monitoreo intensivo por ventana.
  - `extended_monitoring_report_YYYYMMDD_HHMMSS.json`: monitoreo extendido y estadísticas agregadas.

- REPORTS_DIR (`reports/`):
  - `audits/`: auditorías de integridad y forenses.
  - `incidents/`: reportes de paradas de emergencia e incidentes.
  - `safety/`: validaciones de seguridad previas a real trading.
  - `stabilization/`: resultados de estabilizaciones masivas.
  - `performance/`: evaluaciones de rendimiento y ajustes.
  - `integrity/`: resultados de pruebas de integridad (sistema y componentes).
  - `phase8/`: reportes de activación por fases.
  - `plans/`: planes de activación, reactivación, estabilización y monitoreo.

### 🗄️ Políticas de retención y rotación

- MONITORING_DIR
  - `monitoring_summary_*`: retener 90 días; comprimir >30 días a `.ndjson.gz` (batch semanal).
  - `continuous_72h_monitoring_data_*`: retener 30 días.
  - `intensive_monitoring_report_*` y `extended_monitoring_report_*`: retener 90 días.

- REPORTS_DIR
  - `audits/`, `incidents/`, `safety/`: retener 365 días (cumplimiento y trazabilidad).
  - `stabilization/`, `performance/`, `integrity/`: retener 180 días.
  - `phase8/`, `plans/`: retener 365 días (historial de decisiones).

- Tests
  - `tests/reports/`: retener 14 días (artefactos efímeros de pruebas).

Sugerencia operativa: ejecutar un job semanal que
1) comprima resúmenes de monitoreo >30 días a `.ndjson.gz`,
2) elimine artefactos que excedan su retención,
3) exporte métricas de limpieza (archivos purgados, espacio liberado).
