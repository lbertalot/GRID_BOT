# 📄 Product Requirements Document (PRD) – Trading Backend

## 1. Executive Summary
Sistema algorítmico de trading para Binance.  
Objetivo: ejecución robusta y aprendizaje continuo con PnL positivo y control de riesgos.

## 2. Contexto y Benchmark
- Mercado: herramientas de trading algorítmico, bots low-code/no-code y plataformas de copy-trading.
- Comparables: Kryll.io, Shrimpy, 3Commas, HaasOnline.
- Diferencial de GridBot v2.5:
  - ML online (River) + modelos deep (LSTM/Transformer) para detectar régimen y ajustar estrategias.
  - Defensas by-design: validación previa a cada orden (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL, balance suficiente) y circuit breakers multinivel.
  - Reconciliación financiera determinística (≤ 60 s) y observabilidad integral (Prometheus/Grafana).

## 3. User Personas
| Persona     | Necesidad                           |
|--------------|-----------------------------------|
| Trader Prop  | PnL, control de exposición         |
| DevOps/SRE   | Despliegue seguro, alertas rápidas |
| Gerencia     | KPIs de rentabilidad y uptime      |

Stakeholders adicionales:
- Quant/ML: calibración de Kelly fraccional, validación de modelos y señales.
- Soporte/Operaciones: playbooks de emergencia y monitoreo 24/7.

## 4. Historias de Usuario / Requisitos de Alto Nivel
- Como trader, quiero ejecutar órdenes en ≤250 ms P99 para no perder oportunidades.
- Como SRE, necesito circuit breakers activables para frenar pérdidas.
- Como quant, quiero ajustar el tamaño por Kelly fraccional bajo límites conservadores.
- Como gerente, quiero ver KPIs de desempeño y estabilidad en un dashboard.

## 5. KPIs y Métricas de Éxito
- **Uptime API** ≥ 99.9 %.
- **Reconciliación financiera** ≤ 60 s.
- **Latencia P99** ≤ 250 ms.
- Rentabilidad mensual ≥ benchmark del mercado.
- **Integridad**: discrepancia de balance ≤ 0.1% sostenida 24 h.
- **Calidad**: cobertura tests ≥ 85%; 0 errores de precisión en 72 h.
- **Sincronización**: 0 errores de timestamp (-1021) en 24h.
- **Precisión**: 0 errores de LOT_SIZE (-1013) y precisión (-1111) en 24h.
- **Liquidez**: Auto-rebalancer V2 activo con generación de USDT ≥ 25 USDT.
- **Circuit Breakers**: Activación automática en pérdidas ≥ 5% diarias.
- **Métricas Grafana**: Dashboard operativo con datos en tiempo real.

## 6. Criterios de Aceptación
- Pruebas E2E en testnet con >1 000 órdenes sin fallos críticos.
- Dashboards en Grafana mostrando métricas clave.
- Breakers operativos con umbrales por activo y globales; métricas exportadas.
- Registro idempotente de órdenes (éxito/fallo/parcial) y auditorías JSON disponibles.
- **Sincronización temporal**: 0 errores -1021 (timestamp out of sync) en 24h.
- **Validación de precisión**: 0 errores -1013 (LOT_SIZE) y -1111 (precision) en 24h.
- **Auto-rebalancer V2**: Funcionamiento automático con liquidación priorizada.
- **Circuit breakers automáticos**: Activación basada en métricas de pérdidas.
- **Métricas en tiempo real**: Dashboard Grafana con datos actualizados.

## 7. Roadmap
| Fase    | Hito                               |
|---------|-----------------------------------|
| Fase 1  | Validación E2E órdenes y métricas  |
| Fase 2  | ML adaptativo y optimización fees  |
| Fase 3  | Public release parcial (API/docs)  |
| Fase 4  | Reconciliación y tracking robustos  |
| Fase 5  | Reactivación gradual de real trading |

## 8. Riesgos y Mitigaciones
- **API Binance cambiante** → monitoreo y tests contractuales.
- **Latencia red** → redundancia en regiones AWS/GCP.
- **Discrepancias contables** → reconciliación periódica y breakers por discrepancia.
- **Falsos positivos de alertas** → cooldown/dedupe y umbrales calibrados.
- **Model drift** → validación continua y fallback a reglas/estrategias estáticas.
- **Errores de timestamp (-1021)** → configuración UTC en Docker y sincronización automática.
- **Errores de precisión (-1013, -1111)** → validación automática de filtros de Binance.
- **Falta de liquidez USDT** → auto-rebalancer V2 con liquidación priorizada.
- **Circuit breakers inactivos** → sistema automático de activación basado en métricas.
- **Métricas desactualizadas** → actualización manual y monitoreo continuo.

## 9. Prioridades
- Bloqueante: integridad (reconciliación y tracking), validación E2E, breakers.
- Alto: observabilidad financiera y de ejecución, tests E2E, cobertura ≥ 85%.
- Medio: benchmarking competitivo y documentación pública parcial.
