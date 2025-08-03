# 🤖 GridBot Trading Platform

Una plataforma completa de trading automatizado que implementa estrategias avanzadas de trading algorítmico, incluyendo Grid Trading, DCA, Scalping y más.

## 🚀 Características Principales

### 📊 Trading Automatizado
- **Grid Trading**: Estrategia de trading en rangos de precios
- **DCA (Dollar Cost Averaging)**: Compra automática periódica
- **Scalping**: Trading de alta frecuencia
- **Arbitraje**: Oportunidades entre exchanges

### 🧠 Machine Learning
- Predicción de precios con modelos ML
- Optimización automática de parámetros
- Detección de patrones de mercado
- Backtesting avanzado

### 📈 Monitoreo y Análisis
- Dashboard en tiempo real
- Métricas de rendimiento avanzadas
- Alertas automáticas por Telegram
- Análisis de riesgo integrado

### 🔒 Gestión de Riesgos
- Stop-loss automático
- Position sizing dinámico
- Límites de exposición por activo
- Rebalanceo automático

### 🌐 Escalabilidad
- Arquitectura multi-tenant
- Soporte multi-exchange
- API pública documentada
- White-label solutions

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

### Grafana
- **URL**: http://localhost:3000
- **Usuario**: admin
- **Contraseña**: gridbot123
- **Dashboards**: Trading, Performance, System Health

### Alertas
- **Telegram**: Alertas automáticas de trading
- **Email**: Alertas de sistema (configurable)
- **Slack**: Integración opcional

## 🔧 Desarrollo

### Estructura del Proyecto
```
grid-bot/
├── app/                    # Código de la aplicación
│   ├── api/               # Endpoints de la API
│   ├── core/              # Configuración y utilidades
│   ├── models/            # Modelos de base de datos
│   ├── services/          # Lógica de negocio
│   ├── strategies/        # Estrategias de trading
│   └── templates/         # Templates HTML
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
```

### Tests Disponibles
- **Unit Tests**: Funciones individuales
- **Integration Tests**: APIs y servicios
- **E2E Tests**: Flujos completos
- **Performance Tests**: Carga y estrés

## 📈 Roadmap

### Fase 1: MVP (Q1 2025) ✅
- [x] Sistema de rebalanceo automático
- [x] Dashboard de rendimiento
- [x] Gestión de riesgos básica
- [x] Notificaciones Telegram

### Fase 2: Mejoras Core (Q2 2025) 🚧
- [ ] Múltiples estrategias de trading
- [ ] Machine learning básico
- [ ] API pública
- [ ] Backtesting avanzado

### Fase 3: Escalabilidad (Q3 2025) 📋
- [ ] Arquitectura multi-tenant
- [ ] Multi-exchange support
- [ ] Marketplace de estrategias
- [ ] White-label solutions

### Fase 4: Enterprise (Q4 2025) 📋
- [ ] Integraciones enterprise
- [ ] Reporting avanzado
- [ ] Compliance tools
- [ ] Professional services

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
- [Guía de Usuario](docs/USER_GUIDE.md)
- [API Documentation](docs/API.md)
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

---

**Desarrollado con ❤️ por el equipo GridBot**
