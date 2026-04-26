## GridBot v2.5 – Portal de Documentación

Bienvenido. Este portal centraliza la documentación técnica y operativa para desarrollar, operar y mantener GridBot v2.5.

### Getting Started (15 min)
```bash
git clone https://github.com/ORG/REPO.git
cd REPO
cp env.example .env
docker compose --profile production up -d db redis prometheus grafana api
curl -s http://localhost:8000/health | jq
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET
```

### Navegación rápida
- Introducción → visión del proyecto y stack
- Arquitectura → componentes, diagrama y flujo E2E
- Instalación → entorno local y verificación
- Conceptos Clave → grid, rebalanceo, breakers, observabilidad, reconciliación
- Flujo de Desarrollo → estilo, tests, contribución
- How-to → tareas operativas frecuentes
- Troubleshooting → resolución por categorías

### Enlaces clave
- PRD: requisitos de producto
- FSD: especificaciones funcionales
- OpenAPI: esquema de endpoints
- Notas de versión: cambios relevantes por release
