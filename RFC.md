# RFC - GridBot Trading Platform

## RFC-001: Arquitectura de Trading Automatizado con Machine Learning

**Estado**: Propuesto  
**Autor**: Equipo GridBot  
**Fecha**: Enero 2025  
**Versión**: 2.0.0  

---

## 1. Resumen

Este RFC propone la arquitectura completa para GridBot Trading Platform, una solución de trading automatizado que combina estrategias tradicionales de grid trading con machine learning para optimizar el rendimiento en mercados de criptomonedas.

## 2. Motivación

### 2.1 Problemas Identificados
- **Falta de automatización**: Los traders manuales pierden oportunidades por limitaciones humanas
- **Gestión de riesgos inadecuada**: Falta de límites automáticos y stop-loss
- **Optimización manual**: Parámetros de trading no optimizados dinámicamente
- **Monitoreo limitado**: Falta de métricas en tiempo real y alertas

### 2.2 Oportunidades
- **Mercado creciente**: El trading de criptomonedas está en expansión
- **Tecnología disponible**: APIs maduras de exchanges como Binance
- **Machine Learning**: Algoritmos capaces de adaptarse a cambios de mercado
- **Automatización**: Reducción de errores humanos y operación 24/7

## 3. Diseño de Alto Nivel

### 3.1 Arquitectura General

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   Trading       │
│   (React)       │◄──►│   (Nginx)       │◄──►│   Engine        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Redis         │    │   Celery        │
│   (Database)    │◄──►│   (Cache)       │◄──►│   (Tasks)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │    │   Grafana       │    │   Alertmanager  │
│   (Metrics)     │◄──►│   (Dashboards)  │◄──►│   (Alerts)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 3.2 Componentes Principales

#### 3.2.1 OptimizedGridManager
```python
class OptimizedGridManager:
    """
    Gestor principal de grid trading con optimizaciones
    """
    def __init__(self, config: GridManagerConfig):
        self.config = config
        self.client = self._initialize_binance_client()
        self.order_validator = OrderValidator(self.client)
        self.trading_history: List[TradingResult] = []
        self.asset_limits: Dict[str, AssetLimit] = {}
        self.insufficient_funds: Dict[str, Dict] = {}
        self.async_binance = AsyncBinanceWrapper()
    
    async def execute_grid_trading_cycle(self) -> List[TradingResult]:
        """Ejecuta un ciclo completo de grid trading"""
        
    def calculate_optimal_quantities(self, balances: Dict[str, float], 
                                   prices: Dict[str, float]) -> Dict[str, float]:
        """Calcula cantidades óptimas para operar"""
        
    async def _execute_trade(self, symbol: str, action: str, 
                           quantity: float, price: float) -> Optional[TradingResult]:
        """Ejecuta una operación de trading"""
```

#### 3.2.2 RiskManager
```python
class RiskManager:
    """
    Sistema de gestión de riesgos integral
    """
    def __init__(self):
        self.max_daily_loss_percentage = 0.05  # 5%
        self.max_position_size_percentage = 0.20  # 20%
        self.max_total_exposure_percentage = 0.80  # 80%
        self.stop_loss_percentage = 0.10  # 10%
        self.max_drawdown_percentage = 0.15  # 15%
        self.trading_enabled = True
        self.emergency_stop = False
    
    async def check_portfolio_risk(self) -> RiskStatus:
        """Verifica el riesgo general del portafolio"""
        
    async def calculate_risk_metrics(self) -> RiskMetrics:
        """Calcula métricas de riesgo detalladas"""
        
    async def set_emergency_stop(self, enabled: bool):
        """Activa/desactiva parada de emergencia"""
```

#### 3.2.3 CommissionManager
```python
class CommissionManager:
    """
    Gestor de comisiones para validar rentabilidad
    """
    def __init__(self):
        self.default_maker_commission = 0.001  # 0.1%
        self.default_taker_commission = 0.001  # 0.1%
        self._commission_cache = {}
        self._symbol_info_cache = {}
    
    def calculate_commission(self, notional_value: float, 
                           order_type: str = 'MARKET', 
                           symbol: str = None) -> float:
        """Calcula comisión para una operación"""
        
    def validate_grid_profitability(self, symbol: str, min_price: float,
                                  max_price: float, quantity: float,
                                  num_levels: int, min_profit_percentage: float) -> Dict:
        """Valida rentabilidad de estrategia grid"""
```

#### 3.2.4 MLEngine
```python
class MLEngine:
    """
    Motor de machine learning para detección de régimen de mercado
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "data/ml/regime_model.joblib"
        self.metric = None
        self.drift_detector = ADWIN()
        self.pipeline = None
        self._init_or_load_model()
        self.collector = MarketDataCollector()
    
    async def train_on_symbol(self, symbol: str, interval: str = "1m", 
                            limit: int = 60) -> None:
        """Entrena incrementalmente con datos recientes"""
        
    async def predict_regime(self, symbol: str, interval: str = "1m", 
                           limit: int = 60) -> RegimePrediction:
        """Predice régimen de mercado (alcista/bajista)"""
```

## 4. Especificaciones Técnicas

### 4.1 APIs y Endpoints

#### 4.1.1 Trading APIs
```python
# Trading básico
POST /api/trade/order
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.001,
    "price": 45000.0
}

# Grid trading
POST /api/trade/run_grid
{
    "symbol": "BTCUSDT",
    "min_price": 44000.0,
    "max_price": 46000.0,
    "grids": 10,
    "quantity": 0.001
}

# Balances
GET /api/trade/balances
Response: {
    "BTC": 0.1,
    "ETH": 1.5,
    "USDT": 1000.0
}
```

#### 4.1.2 Estrategias APIs
```python
# Crear estrategia
POST /api/v1/strategies/create
{
    "symbol": "BTCUSDT",
    "strategy_type": "DCA",
    "investment_amount": 100.0,
    "risk_tolerance": 0.5,
    "frequency_hours": 24,
    "max_investments": 10
}

# Ejecutar estrategia
POST /api/v1/strategies/execute
{
    "strategy_id": "uuid",
    "force": false
}
```

#### 4.1.3 Configuración APIs
```python
# Optimizar configuración
POST /api/v1/config/optimize
{
    "symbol": "BTCUSDT",
    "strategy": "grid_optimization",
    "investment_amount": 100.0,
    "risk_tolerance": 0.5,
    "max_grids": 20,
    "time_horizon": 7
}

# Análisis de mercado
GET /api/v1/config/market-analysis/BTCUSDT
Response: {
    "symbol": "BTCUSDT",
    "current_price": 45000.0,
    "volatility": {
        "value": 0.15,
        "level": "Media"
    },
    "trend": "Alcista",
    "volume_24h": 1000000.0
}
```

### 4.2 Modelos de Datos

#### 4.2.1 Trade Model
```python
class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY/SELL
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    profit_loss = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
```

#### 4.2.2 GridConfig Model
```python
class GridConfig(Base):
    __tablename__ = "grid_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    min_price = Column(Float)
    max_price = Column(Float)
    grids = Column(Integer)
    quantity = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 4.2.3 PerformanceMetrics Model
```python
class PerformanceMetrics(Base):
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    volatility = Column(Float)
    win_rate = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
```

### 4.3 Configuración de Docker

#### 4.3.1 docker-compose.yml
```yaml
version: '3.8'

services:
  # Base de datos
  db:
    build: ./docker/postgres
    environment:
      POSTGRES_USER: griduser
      POSTGRES_PASSWORD: gridpass
      POSTGRES_DB: gridbot
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U griduser -d gridbot"]
      interval: 30s
      timeout: 10s
      retries: 3

  # API principal
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

  # Celery worker
  celery_worker:
    build: .
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - .env
    command: celery -A app.core.celery_app worker --loglevel=info --concurrency=2

  # Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  # Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=gridbot123
    volumes:
      - ./docker/grafana/provisioning:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana

volumes:
  pgdata:
  prometheus_data:
  grafana_data:
```

## 5. Implementación

### 5.1 Estructura de Directorios
```
grid-bot/
├── app/
│   ├── api/                    # Endpoints de la API
│   │   ├── trade.py           # Trading básico
│   │   ├── strategies.py      # Estrategias
│   │   ├── config_routes.py   # Configuración
│   │   ├── risk_routes.py     # Gestión de riesgos
│   │   ├── metrics_routes.py  # Métricas
│   │   └── commission_routes.py # Comisiones
│   ├── core/                  # Componentes core
│   │   ├── optimized_grid_manager.py
│   │   ├── risk_manager.py
│   │   ├── commission_manager.py
│   │   ├── metrics_manager.py
│   │   └── celery_app.py
│   ├── services/              # Servicios
│   │   ├── binance_service.py
│   │   ├── auto_rebalancer.py
│   │   ├── ml_engine.py
│   │   ├── telegram_alert.py
│   │   └── strategy_factory.py
│   ├── models/                # Modelos de BD
│   ├── schemas/               # Esquemas Pydantic
│   └── main.py               # Aplicación principal
├── docker/                   # Configuración Docker
├── scripts/                  # Scripts de utilidad
├── tests/                    # Tests
└── requirements.txt          # Dependencias
```

### 5.2 Dependencias Principales
```txt
# FastAPI y servidor web
fastapi==0.104.1
uvicorn[standard]==0.24.0

# Base de datos
SQLAlchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

# Trading
python-binance==1.0.19
ccxt==4.1.77

# Machine Learning
numpy==1.24.3
pandas==2.1.4
scikit-learn==1.3.2
river==0.20.1

# Monitoreo
prometheus-client==0.19.0
celery==5.3.4
redis==5.0.1

# Validación
pydantic==2.5.0
pydantic-settings==2.1.0
```

### 5.3 Variables de Entorno
```bash
# Binance API
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET_KEY=tu_secret_key
BINANCE_TESTNET=false

# Base de Datos
DATABASE_URL=postgresql://griduser:gridpass@db:5432/gridbot
POSTGRES_USER=griduser
POSTGRES_PASSWORD=gridpass
POSTGRES_DB=gridbot

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Telegram
TELEGRAM_BOT_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id

# Configuración
PAPER_TRADING=false
SECRET_KEY=tu_secret_key
DEBUG=true
```

## 6. Métricas y Monitoreo

### 6.1 Métricas de Prometheus
```python
# Métricas de rentabilidad
profit_total_usdt = Gauge('profit_total_usdt', 'Ganancia total acumulada en USDT', ['strategy'])
roi_daily_percent = Gauge('roi_daily_percent', 'ROI diario en porcentaje', ['strategy'])
portfolio_total_value_usdt = Gauge('portfolio_total_value_usdt', 'Valor total del portafolio en USDT', ['strategy'])

# Métricas de trading
trades_executed_total = Counter('trades_executed_total', 'Total de trades ejecutados', ['side', 'asset', 'strategy'])
trades_success_rate = Gauge('trades_success_rate', 'Tasa de éxito de trades (0-1)', ['strategy'])

# Métricas de rendimiento
trade_execution_duration = Histogram('trade_execution_duration_seconds', 'Duración de ejecución de trades', ['asset', 'strategy'])
grid_cycle_duration_seconds = Histogram('grid_cycle_duration_seconds', 'Duración del ciclo grid en segundos')

# Métricas de API
api_requests_total = Counter('api_requests_total', 'Total de requests de API', ['method', 'endpoint', 'status_code'])
api_request_duration = Histogram('api_request_duration_seconds', 'Duración de requests de API', ['method', 'endpoint'])
```

### 6.2 Dashboards de Grafana
- **Trading Overview**: Resumen general de operaciones
- **Performance Metrics**: Métricas de rendimiento
- **Risk Management**: Gestión de riesgos
- **System Health**: Salud del sistema

### 6.3 Alertas
```yaml
# alertmanager.yml
route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'telegram-notifications'

receivers:
- name: 'telegram-notifications'
  telegram_configs:
  - bot_token: '{{ .TELEGRAM_BOT_TOKEN }}'
    chat_id: '{{ .TELEGRAM_CHAT_ID }}'
    message: '🚨 {{ .CommonAnnotations.summary }}'
```

## 7. Testing

### 7.1 Tests Unitarios
```python
# test_grid_manager.py
def test_calculate_grid_levels():
    levels = calculate_grid_levels(100, 200, 5)
    assert len(levels) == 5
    assert levels[0] == 100
    assert levels[-1] == 200

def test_decide_grid_action():
    levels = [100, 125, 150, 175, 200]
    action = decide_grid_action(130, levels, None)
    assert action["action"] == "BUY"
    assert action["level"] == 125
```

### 7.2 Tests de Integración
```python
# test_trading_integration.py
async def test_complete_trading_cycle():
    manager = await create_optimized_grid_manager('test_config.json')
    results = await manager.execute_grid_trading_cycle()
    assert len(results) >= 0
    assert all(isinstance(r, TradingResult) for r in results)
```

### 7.3 Tests de Performance
```python
# test_performance.py
def test_api_response_time():
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    assert response.elapsed.total_seconds() < 0.1
```

## 8. Seguridad

### 8.1 Autenticación
```python
def get_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    api_key = credentials.credentials
    valid_api_key = os.getenv("API_KEY")
    
    if api_key != valid_api_key:
        raise HTTPException(status_code=401, detail="API key inválido")
    
    return api_key
```

### 8.2 Validación de Input
```python
class OrderRequest(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z0-9]+USDT$')
    side: str = Field(..., regex=r'^(BUY|SELL)$')
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        if v not in VALID_SYMBOLS:
            raise ValueError('Símbolo no válido')
        return v
```

### 8.3 Rate Limiting
```python
class RateLimiter:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.timestamp = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
```

## 9. Despliegue

### 9.1 Script de Inicio
```bash
#!/bin/bash
# scripts/start.sh

echo "🚀 Iniciando GridBot Trading Platform..."

# Verificar variables de entorno
if [ -z "$BINANCE_API_KEY" ] || [ -z "$BINANCE_SECRET_KEY" ]; then
    echo "❌ Error: Variables de entorno de Binance no configuradas"
    exit 1
fi

# Construir e iniciar servicios
docker-compose build
docker-compose up -d

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios estén listos..."
sleep 30

# Verificar estado
./scripts/verify_deployment.py

echo "✅ GridBot iniciado correctamente"
echo "📊 Grafana: http://localhost:3000 (admin/gridbot123)"
echo "📈 Prometheus: http://localhost:9090"
echo "🔧 API: http://localhost:8000"
```

### 9.2 Verificación de Despliegue
```python
# scripts/verify_deployment.py
import requests
import time

def verify_service(url: str, name: str) -> bool:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ {name}: OK")
            return True
        else:
            print(f"❌ {name}: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def main():
    services = [
        ("http://localhost:8000/health", "API"),
        ("http://localhost:3000/api/health", "Grafana"),
        ("http://localhost:9090/-/healthy", "Prometheus"),
        ("http://localhost:5555", "Flower")
    ]
    
    all_ok = True
    for url, name in services:
        if not verify_service(url, name):
            all_ok = False
    
    if all_ok:
        print("🎉 Todos los servicios están funcionando correctamente")
    else:
        print("⚠️ Algunos servicios tienen problemas")
        exit(1)

if __name__ == "__main__":
    main()
```

## 10. Consideraciones Futuras

### 10.1 Escalabilidad
- **Multi-tenant**: Soporte para múltiples usuarios
- **Multi-exchange**: Integración con otros exchanges
- **Microservicios**: Separación en servicios independientes
- **Kubernetes**: Orquestación de contenedores

### 10.2 Machine Learning Avanzado
- **Deep Learning**: Redes neuronales para predicción
- **Reinforcement Learning**: Aprendizaje por refuerzo
- **Ensemble Methods**: Combinación de múltiples modelos
- **Feature Engineering**: Extracción automática de features

### 10.3 Integraciones
- **TradingView**: Integración con alertas
- **Discord**: Notificaciones en Discord
- **Slack**: Alertas empresariales
- **Webhooks**: Integración con sistemas externos

## 11. Conclusión

Este RFC propone una arquitectura robusta y escalable para GridBot Trading Platform, combinando las mejores prácticas de desarrollo con tecnologías modernas de machine learning y monitoreo. La implementación modular permite una evolución gradual y la adición de nuevas funcionalidades sin afectar la estabilidad del sistema.

### 11.1 Próximos Pasos
1. **Revisión del RFC**: Feedback de stakeholders
2. **Implementación**: Desarrollo iterativo
3. **Testing**: Validación exhaustiva
4. **Despliegue**: Lanzamiento gradual
5. **Monitoreo**: Seguimiento continuo

### 11.2 Métricas de Éxito
- **Uptime**: > 99.9%
- **ROI**: > 5% mensual
- **Sharpe Ratio**: > 1.5
- **User Satisfaction**: > 4.5/5

---

**RFC-001** - GridBot Trading Platform Architecture  
**Estado**: Propuesto  
**Autor**: Equipo GridBot  
**Fecha**: Enero 2025  
**Versión**: 2.0.0
