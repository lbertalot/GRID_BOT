# Workflow Ops watch + Antigravity (GridBot)

Este documento enlaza el esqueleto en `scripts/ops_watch/` con **skills de Antigravity** para análisis, depuración y despliegue **graduado**.

## Origen de datos

1. Ejecutar una recolección local (o vía cron cada 10 min):

   ```bash
   make ops-watch-once
   ```

2. Abrir `reports/ops_watch/LATEST.md` y, si hace falta, el `raw_*.log` referenciado en `LATEST.meta.json`.

## Uso con `@antigravity-workflows`

En el IDE o Antigravity:

```text
Use @antigravity-workflows y ejecuta el workflow "Observability Docker Ops Agent"
con el informe en reports/ops_watch/LATEST.md y el contexto del repo grid_bot.
```

El workflow está definido en el catálogo de *antigravity-awesome-skills* (`data/workflows.json`, id `observability-docker-ops-agent`).

## Secuencia manual de skills (equivalente)

| Fase | Objetivo | Skills sugeridos |
|------|----------|------------------|
| 1. Triage de logs | Clasificar ruido vs incidente real | `@error-detective`, `@observability-engineer` |
| 2. Hipótesis | No saltar a parches sin causa | `@systematic-debugging`, `@phase-gated-debugging` |
| 3. Cambio de código | Solo con criterios de aceptación | `@test-driven-development`, `@bug-hunter` |
| 4. Verificación | Tests + salud antes de desplegar | `@verification-before-completion`, `@lint-and-validate` |
| 5. Despliegue local | Compose rebuild controlado | `@devops-deploy`, `@bash-defensive-patterns` |
| 6. Cierre | Evidencia y riesgos residuales | `@closed-loop-delivery` o notas tipo postmortem liviano |

## Niveles de automatización (recomendación)

- **Nivel 0 (actual esqueleto):** solo `run_once.py` + informes; el humano o el agente invocan skills con contexto.
- **Nivel 1:** el mismo + notificación (Telegram ya integrado en el proyecto) si `health != green`.
- **Nivel 2:** agente que abre PR con diff; CI valida; merge humano.
- **Nivel 3:** redeploy automático — solo en **staging** o con trading desactivado por diseño.

## Archivos relacionados

- `scripts/ops_watch/README.md` — opciones CLI y cron
- `scripts/ops_watch/config.example.json` — plantilla de configuración

## Skills adoptados en el ciclo de calidad (2026-04-26)

Estos skills se incorporaron al pipeline de CI/CD y al flujo TDD como parte del
trabajo de hardening descripto en
[`AGENTS.md` § Agentes de Calidad y CI/CD](../AGENTS.md) y
[`docs/CICD_RUNBOOK.md`](CICD_RUNBOOK.md).

| Skill | Fase | Para qué se usa |
|---|---|---|
| `@systematic-debugging` | Diagnóstico | Mapeo evidencia → hipótesis → fix sin parches al ojo |
| `@find-bugs` | Diagnóstico | Lectura del cobertura/output para detectar tests rotos por drift |
| `@bug-hunter` | Reparación de tests | Cazar la causa raíz de un test que no rompe por *assert* sino por import/fixture |
| `@phase-gated-debugging` | Reparación de tests | Bloquea fixes hasta confirmar root cause |
| `@tdd-orchestrator` | Cobertura crítica | Coordina ciclos RED-GREEN-REFACTOR en tareas grandes |
| `@test-driven-development` | Cobertura crítica | TDD estricto en cada nuevo test P1 |
| `@cicd-automation-workflow-automate` | CI/CD | Diseño del gate escalonado de cobertura y del job `security-scan` |
| `@github-actions-templates` | CI/CD | Patrones para los 6 jobs del pipeline |
| `@documentation-generation-doc-generate` | Documentación | Generación de `TDD_WORKFLOW.md` y `CICD_RUNBOOK.md` |
| `@agents-md` | Documentación | Sección "Agentes de Calidad y CI/CD" en `AGENTS.md` |
| `@verification-before-completion` | Verificación | Checklist antes de declarar la fase como hecha |
| `@lint-and-validate` | Verificación | Pre-commit local sobre lo modificado |

Para el ciclo de **observabilidad / runtime** se sigue usando la tabla original
de §"Secuencia manual de skills (equivalente)".
