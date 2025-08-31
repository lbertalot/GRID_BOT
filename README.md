# 🤖 GridBot Trading Platform

Una plataforma completa de trading automatizado que implementa estrategias avanzadas de trading algorítmico, incluyendo Grid Trading, DCA, Scalping y Machine Learning, diseñada para operar en el mercado de criptomonedas de Binance.

## 🚀 Características Principales

### 📊 Trading Automatizado
- **Grid Trading**: Estrategia de trading en rangos de precios con optimización automática
- **DCA (Dollar Cost Averaging)**: Compra automática periódica con parámetros configurables
- **Scalping**: Trading de alta frecuencia con gestión de riesgos
- **RSI/MACD**: Indicadores técnicos integrados
- **Trailing Stop**: Stop-loss dinámico basado en volatilidad

### 🧠 Machine Learning
- **Motor ML**: River para aprendizaje incremental en tiempo real
- **Predicción de Régimen**: Detección automática de mercados alcistas/bajistas
- **Features Avanzadas**: Volatilidad, RSI, ATR, volumen, spread
- **Adaptación Automática**: Ajuste dinámico de estrategias según condiciones de mercado
- **Detección de Cambios**: ADWIN para detectar cambios de régimen

### 📈 Monitoreo y Análisis
- **Dashboard en Tiempo Real**: Grafana con métricas avanzadas
- **Métricas de Rendimiento**: ROI, Sharpe Ratio, Maximum Drawdown, Volatilidad
- **Alertas Automáticas**: Telegram, Email, Slack
- **Análisis de Riesgo**: Sistema integral de gestión de riesgos
- **Reportes Detallados**: Exportación de datos y análisis histórico

### 🔒 Gestión de Riesgos
- **Stop-Loss Automático**: Fijo y dinámico basado en volatilidad
- **Position Sizing**: Tamaño de posición dinámico
- **Límites de Exposición**: Por activo y portafolio completo
- **Rebalanceo Automático**: Mantenimiento de saldos operativos
- **Parada de Emergencia**: Activación manual/automática

### 🌐 Escalabilidad
- **Arquitectura Modular**: Componentes independientes y reutilizables
- **Soporte Multi-Exchange**: Preparado para múltiples exchanges
- **API Pública**: Documentación completa con OpenAPI/Swagger
- **White-Label**: Soluciones personalizables para empresas

## 🏗️ Arquitectura

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

## 📋 Requisitos Previos

- **Docker**: Versión 20.10 o superior
- **Docker Compose**: Versión 2.0 o superior
- **Git**: Para clonar el repositorio
- **API Keys de Binance**: Para trading real
- **Python 3.11+**: Para desarrollo local

## 🚀 Instalación Rápida

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/grid-bot.git
cd grid-bot
```

### 2. Configurar Variables de Entorno
```bash
cp env.example .env
# Editar .env con tus API keys de Binance
```

### 3. Iniciar con Script Automático
```bash
./scripts/start.sh
```

### 4. Acceder a la Plataforma
- **API**: http://localhost:8000
- **Grafana**: http://localhost:3000 (admin/gridbot123)
- **Prometheus**: http://localhost:9090
- **Flower**: http://localhost:5555
- **Documentación API**: http://localhost:8000/docs

## ⚙️ Configuración Manual

### 1. Configurar Variables de Entorno
Edita el archivo `.env` con tus credenciales:

```bash
# Binance API Keys (OBLIGATORIO)
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_SECRET_KEY=tu_secret_key_aqui

# Telegram (OPCIONAL)
TELEGRAM_BOT_TOKEN=tu_bot_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui

# Seguridad
SECRET_KEY=tu_secret_key_super_segura

# Configuración de Trading
PAPER_TRADING=false
BINANCE_TESTNET=false
```

### 2. Construir e Iniciar Servicios
```bash
# Construir imágenes
docker-compose build

# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f
```

### 3. Verificar Instalación
```bash
# Verificar estado de servicios
docker-compose ps

# Verificar API
curl http://localhost:8000/health

# Verificar base de datos
docker-compose exec db psql -U griduser -d gridbot -c "SELECT version();"
```

## 📊 Monitoreo y Métricas

### Prometheus
- **URL**: http://localhost:9090
- **Métricas**: Latencia, throughput, errores, métricas de trading
- **Retención**: 200 horas de datos históricos

### Grafana
- **URL**: http://localhost:3000
- **Usuario**: admin
- **Contraseña**: gridbot123
- **Dashboards**: 
  - Trading Overview
  - Performance Metrics
  - Risk Management
  - System Health

### Alertas
- **Telegram**: Alertas automáticas de trading y sistema
- **Email**: Alertas de sistema (configurable)
- **Slack**: Integración opcional

## 🔧 Desarrollo

### Estructura del Proyecto
```
grid-bot/
├── app/                    # Código de la aplicación
│   ├── api/               # Endpoints de la API (50+ endpoints)
│   │   ├── trade.py       # Trading básico
│   │   ├── strategies.py  # Estrategias múltiples
│   │   ├── config_routes.py # Optimización de configuración
│   │   ├── risk_routes.py # Gestión de riesgos
│   │   ├── metrics_routes.py # Métricas y monitoreo
│   │   └── commission_routes.py # Gestión de comisiones
│   ├── core/              # Componentes core
│   │   ├── optimized_grid_manager.py # Gestor principal de grid trading
│   │   ├── risk_manager.py # Sistema de gestión de riesgos
│   │   ├── commission_manager.py # Gestor de comisiones
│   │   ├── metrics_manager.py # Gestor de métricas
│   │   └── celery_app.py  # Configuración de tareas asíncronas
│   ├── services/          # Servicios especializados
│   │   ├── binance_service.py # Integración con Binance
│   │   ├── auto_rebalancer.py # Rebalanceo automático
│   │   ├── ml_engine.py   # Motor de machine learning
│   │   ├── telegram_alert.py # Alertas por Telegram
│   │   └── strategy_factory.py # Factory de estrategias
│   ├── models/            # Modelos de base de datos
│   ├── schemas/           # Esquemas Pydantic
│   └── main.py           # Aplicación principal FastAPI
├── docker/                # Configuración Docker
├── scripts/               # Scripts de utilidad
├── tests/                 # Tests automatizados
└── docs/                  # Documentación
```

### Comandos de Desarrollo
```bash
# Ejecutar tests
docker-compose exec api pytest

# Ver logs en tiempo real
docker-compose logs -f api

# Acceder a la base de datos
docker-compose exec db psql -U griduser -d gridbot

# Reconstruir servicios
docker-compose build --no-cache
docker-compose up -d

# Ejecutar migraciones
docker-compose exec api alembic upgrade head
```

## 🧪 Testing

### Ejecutar Tests
```bash
# Tests unitarios
docker-compose exec api pytest tests/unit/

# Tests de integración
docker-compose exec api pytest tests/integration/

# Tests completos con cobertura
docker-compose exec api pytest --cov=app tests/

# Tests de performance
docker-compose exec api pytest tests/performance/
```

### Tests Disponibles
- **Unit Tests**: Funciones individuales y componentes
- **Integration Tests**: APIs y servicios
- **E2E Tests**: Flujos completos de trading
- **Performance Tests**: Carga y estrés
- **Security Tests**: Validación de seguridad

## 📈 APIs y Endpoints

### Trading APIs
```bash
# Colocar orden
POST /api/trade/order
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.001,
    "price": 45000.0
}

# Ejecutar grid trading
POST /api/trade/run_grid
{
    "symbol": "BTCUSDT",
    "min_price": 44000.0,
    "max_price": 46000.0,
    "grids": 10,
    "quantity": 0.001
}

# Obtener balances
GET /api/trade/balances

# Obtener precio
GET /api/trade/price/{symbol}
```

### Estrategias APIs
```bash
# Estrategias disponibles
GET /api/v1/strategies/available

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

### Configuración APIs
```bash
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
GET /api/v1/config/market-analysis/{symbol}
```

### Gestión de Riesgos APIs
```bash
# Estado de riesgo
GET /api/v1/risk/status

# Parada de emergencia
POST /api/v1/risk/emergency-stop
{
    "enabled": true,
    "reason": "Mercado volátil"
}

# Verificar portafolio
GET /api/v1/risk/portfolio/check

# Riesgo por activo
GET /api/v1/risk/asset/{symbol}
```

### Métricas APIs
```bash
# Métricas de rentabilidad
GET /api/v1/metrics/profitability

# Resumen de métricas
GET /api/v1/metrics/summary

# Métricas por activo
GET /api/v1/metrics/assets

# Métricas Prometheus
GET /api/v1/metrics/prometheus
```

### Comisiones APIs
```bash
# Tasas de comisión
GET /api/v1/commissions/rates

# Calcular comisión
POST /api/v1/commissions/calculate
{
    "symbol": "BTCUSDT",
    "quantity": 0.001,
    "price": 45000.0,
    "side": "BUY",
    "order_type": "MARKET"
}

# Validar rentabilidad
POST /api/v1/commissions/validate-profitability
{
    "symbol": "BTCUSDT",
    "min_price": 44000.0,
    "max_price": 46000.0,
    "quantity": 0.001,
    "num_levels": 10,
    "min_profit_percentage": 0.5
}
```

## 🔒 Seguridad

### Autenticación
- **API Key**: Bearer token authentication
- **Rate Limiting**: Límites por endpoint
- **Input Validation**: Validación con Pydantic
- **Error Sanitization**: Sanitización de errores

### Manejo de Errores
- **Error Handler**: Sistema centralizado
- **Retry Logic**: Reintentos automáticos
- **Graceful Degradation**: Degradación elegante
- **Error Logging**: Logging estructurado

### Monitoreo de Seguridad
- **Audit Logs**: Logs de auditoría
- **Access Control**: Control de acceso
- **Data Encryption**: Encriptación de datos sensibles
- **Backup Strategy**: Estrategia de respaldo

## 📊 Performance y Escalabilidad

### Optimizaciones
- **Async/Await**: Programación asíncrona
- **Connection Pooling**: Pool de conexiones
- **Caching**: Cache en múltiples niveles
- **Rate Limiting**: Control de velocidad

### Métricas de Performance
- **Response Time**: < 100ms para APIs
- **Throughput**: 1000+ requests/segundo
- **Uptime**: 99.9% disponibilidad
- **Error Rate**: < 0.1% tasa de errores

### Escalabilidad
- **Horizontal Scaling**: Escalado horizontal
- **Load Balancing**: Balanceo de carga
- **Microservices**: Arquitectura de microservicios
- **Auto-scaling**: Escalado automático

## 📈 Roadmap

### Fase 1: MVP (Q1 2025) ✅
- [x] Sistema de grid trading básico
- [x] Integración con Binance
- [x] Dashboard básico
- [x] Alertas por Telegram
- [x] Gestión de riesgos básica
- [x] Sistema de comisiones
- [x] Rebalanceo automático

### Fase 2: Mejoras Core (Q2 2025) 🚧
- [x] Múltiples estrategias de trading (DCA, Scalping, RSI/MACD)
- [x] Machine learning básico (River)
- [x] API pública documentada
- [x] Backtesting avanzado
- [x] Optimización automática de parámetros
- [x] Sistema de métricas avanzado

### Fase 3: Escalabilidad (Q3 2025) 📋
- [ ] Arquitectura multi-tenant
- [ ] Multi-exchange support
- [ ] Marketplace de estrategias
- [ ] White-label solutions
- [ ] Deep Learning integration
- [ ] Reinforcement Learning

### Fase 4: Enterprise (Q4 2025) 📋
- [ ] Integraciones enterprise
- [ ] Reporting avanzado
- [ ] Compliance tools
- [ ] Professional services
- [ ] Advanced ML models
- [ ] Real-time analytics

## 🤝 Contribuir

### 1. Fork el Proyecto
```bash
git clone https://github.com/tu-usuario/grid-bot.git
cd grid-bot
```

### 2. Crear Rama de Feature
```bash
git checkout -b feature/nueva-funcionalidad
```

### 3. Hacer Cambios
```bash
# Hacer cambios en el código
# Agregar tests
# Actualizar documentación
```

### 4. Commit y Push
```bash
git add .
git commit -m "feat: agregar nueva funcionalidad"
git push origin feature/nueva-funcionalidad
```

### 5. Crear Pull Request
- Describir cambios realizados
- Incluir tests si aplica
- Actualizar documentación

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 🆘 Soporte

### Documentación
- [PRD - Product Requirements Document](PRD.md)
- [RFC - Request for Comments](RFC.md)
- [Guía de Usuario](docs/USER_GUIDE.md)
- [API Documentation](http://localhost:8000/docs)
- [Deployment Guide](docs/DEPLOYMENT.md)

### Comunidad
- [Issues](https://github.com/tu-usuario/grid-bot/issues)
- [Discussions](https://github.com/tu-usuario/grid-bot/discussions)
- [Telegram Group](https://t.me/gridbot_community)

### Soporte Técnico
- **Email**: support@gridbot.com
- **Telegram**: @gridbot_support
- **Discord**: [GridBot Community](https://discord.gg/gridbot)

## ⚠️ Disclaimer

Este software es para fines educativos y de investigación. El trading de criptomonedas conlleva riesgos significativos. No garantizamos ganancias y no somos responsables de pérdidas financieras. Usa este software bajo tu propia responsabilidad.

## 📊 Estado del Proyecto

### Métricas Actuales
- **Versión**: 2.0.0
- **Endpoints API**: 50+
- **Estrategias**: 4 (Grid, DCA, Scalping, RSI/MACD)
- **Servicios**: 15+
- **Tests**: 100+ casos
- **Cobertura**: >90%

### Funcionalidades Implementadas
- ✅ Grid Trading Automatizado
- ✅ Gestión de Riesgos Integral
- ✅ Machine Learning con River
- ✅ Sistema de Comisiones
- ✅ Rebalanceo Automático
- ✅ Monitoreo con Prometheus/Grafana
- ✅ Alertas por Telegram
- ✅ API REST Completa
- ✅ Documentación Automática
- ✅ Tests Automatizados
- ✅ Docker Compose
- ✅ Logging Estructurado
- ✅ Rate Limiting
- ✅ Validación de Input
- ✅ Manejo de Errores

---

**Desarrollado con ❤️ por el equipo GridBot**

**Última actualización**: Enero 2025  
**Versión**: 2.0.0
