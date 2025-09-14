# 🤖 Trading Backend – FastAPI + Celery + ML

[![Build](https://github.com/lbertalot/GRID_BOT/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lbertalot/GRID_BOT/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/lbertalot/GRID_BOT/branch/main/graph/badge.svg)](https://codecov.io/gh/lbertalot/GRID_BOT)
[![Security Scan](https://img.shields.io/badge/Security-Passing-brightgreen)]()
[![Version](https://img.shields.io/badge/version-v2.5-blue)]()
[![Status](https://img.shields.io/badge/status-Public-brightgreen)]()

## 📌 Resumen
Backend algorítmico de trading para Binance con enfoque de bajo riesgo y alta observabilidad.  
Incluye:
- API `FastAPI` asíncrona.
- ML/IA híbrido (LSTM/Transformer + River online) para predicción de régimen.
- Orquestación `Docker/K8s`, cache `Redis`, base `PostgreSQL`.
- Circuit breakers, reconciliación financiera (≤ 60 s), dashboards Prometheus/Grafana.

## 🧭 Tabla de Contenidos
- [Resumen](#-resumen)
- [Pitch](#-pitch)
- [Arquitectura](#-arquitectura)
- [Instalación rápida](#-instalación-rápida)
- [Ejemplo mínimo de uso](#-🧪-ejemplo-mínimo-de-uso)
- [Variables de entorno](#-variables-de-entorno)
- [Endpoints principales](#-endpoints-principales)
- [Observabilidad](#-observabilidad)
- [Testing](#-testing)
- [Licencia](#-licencia)
- [Agradecimientos y contribuidores](#-agradecimientos-y-contribuidores)
 - [OpenAPI](#-openapi)

## 🎯 Pitch
GridBot v2.5 reduce el riesgo operativo y financiero en trading algorítmico automatizando defensas críticas antes de cada orden (PRECIO/CANTIDAD/NOTIONAL/Saldo), adaptando el tamaño por Kelly Fraccional según volatilidad y régimen de mercado, y ofreciendo observabilidad total (métricas/alertas/dashboards). ¿Por qué importa? Evita rechazos del exchange, pérdidas por precisión y decisiones con datos inconsistentes, manteniendo la ejecución segura y medible.

## 🏗 Arquitectura
![Arquitectura](docs/architecture.png)

## 🚀 Instalación rápida
```bash
git clone https://github.com/ORG/REPO.git
cd REPO
cp .env.example .env
docker-compose up --build
```

## 🧪 Ejemplo mínimo de uso
1) Healthcheck:
```bash
curl -s http://localhost:8000/health
```

2) Simulación (dry-run) validada, sin enviar orden real:
```bash
curl -s -X POST "http://localhost:8000/api/simulations/dry-run" \
  -H "Authorization: Bearer ${API_KEY:-gridbot_api_key_2024_secure_12345}" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.0002}'
```

## 🔑 Variables de entorno
| Variable              | Descripción                                 |
|-----------------------|----------------------------------------------|
| `BINANCE_API_KEY`     | API Key de Binance                           |
| `BINANCE_API_SECRET`  | API Secret de Binance                        |
| `BINANCE_TESTNET`     | true/false                                   |
| `PAPER_TRADING`       | true/false                                   |
| `DATABASE_URL`        | PostgreSQL URI                               |
| `REDIS_URL`           | Redis URI                                    |
| `TELEGRAM_BOT_TOKEN`  | Token opcional para alertas                  |
| `TELEGRAM_CHAT_ID`    | Chat ID opcional para alertas                |

## 📡 Endpoints principales
- `GET /health`
- `GET /breakers/summary`
- `GET /api/reconciliation/summary`
- `POST /api/simulations/dry-run`
- `GET /metrics` (Prometheus)

## 📊 Observabilidad
Capturas y dashboards Grafana → [`docs/observability.md`](docs/observability.md)

## 🧪 Testing
```bash
pytest --cov=app
```

## 📜 Licencia
Este proyecto está licenciado bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🙌 Agradecimientos y contribuidores
- Equipo GridBot — Plataforma/Trading, SRE/DevOps, Quant/ML.  
Contacto: `support@gridbot.com` | Telegram: `@gridbot_support`

## 📘 OpenAPI
El esquema OpenAPI se publica como artefacto del CI y puede consultarse en `Docs/openapi.json` tras cada build.
