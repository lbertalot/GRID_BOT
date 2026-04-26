"""
Grafana Metrics - Módulo de Grafana Simplificado
GridBot v2.5 - Componente de Integridad Integrado
"""

import logging
from typing import Union
from datetime import datetime

logger = logging.getLogger(__name__)


class GrafanaMetrics:
    """Clase simplificada de métricas de Grafana para componentes de integridad"""

    def __init__(self):
        self.logger = logger
        self.metrics_buffer = []
        self.logger.info(
            "🔧 Módulo de métricas de Grafana inicializado (modo simulado)"
        )

    async def record_metric(
        self, metric_name: str, value: Union[int, float, str]
    ) -> bool:
        """Registrar métrica en Grafana (simulado)"""
        try:
            metric_record = {
                "timestamp": datetime.now().isoformat(),
                "metric_name": metric_name,
                "value": value,
                "type": type(value).__name__,
            }

            self.metrics_buffer.append(metric_record)

            # Mantener solo las últimas 1000 métricas en memoria
            if len(self.metrics_buffer) > 1000:
                self.metrics_buffer = self.metrics_buffer[-1000:]

            self.logger.debug(f"📊 Métrica registrada: {metric_name} = {value}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error registrando métrica {metric_name}: {e}")
            return False

    def record_metric_sync(
        self, metric_name: str, value: Union[int, float, str]
    ) -> bool:
        """Registrar métrica en Grafana (versión síncrona)"""
        try:
            metric_record = {
                "timestamp": datetime.now().isoformat(),
                "metric_name": metric_name,
                "value": value,
                "type": type(value).__name__,
            }

            self.metrics_buffer.append(metric_record)

            # Mantener solo las últimas 1000 métricas en memoria
            if len(self.metrics_buffer) > 1000:
                self.metrics_buffer = self.metrics_buffer[-1000:]

            self.logger.debug(f"📊 Métrica registrada: {metric_name} = {value}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error registrando métrica {metric_name}: {e}")
            return False

    def get_metrics_summary(self) -> dict:
        """Obtener resumen de métricas registradas"""
        if not self.metrics_buffer:
            return {"total_metrics": 0, "metrics": []}

        # Agrupar métricas por nombre
        metrics_by_name = {}
        for metric in self.metrics_buffer:
            name = metric["metric_name"]
            if name not in metrics_by_name:
                metrics_by_name[name] = []
            metrics_by_name[name].append(metric)

        # Calcular estadísticas
        summary = {
            "total_metrics": len(self.metrics_buffer),
            "unique_metrics": len(metrics_by_name),
            "last_metric_timestamp": self.metrics_buffer[-1]["timestamp"]
            if self.metrics_buffer
            else None,
            "metrics_by_name": {},
        }

        for name, metrics in metrics_by_name.items():
            values = [
                m["value"] for m in metrics if isinstance(m["value"], (int, float))
            ]
            if values:
                summary["metrics_by_name"][name] = {
                    "count": len(metrics),
                    "latest_value": metrics[-1]["value"],
                    "min_value": min(values),
                    "max_value": max(values),
                    "avg_value": sum(values) / len(values),
                }

        return summary

    def clear_metrics(self):
        """Limpiar buffer de métricas"""
        self.metrics_buffer.clear()
        self.logger.info("🧹 Buffer de métricas limpiado")

    def export_metrics(self, filename: str = None) -> bool:
        """Exportar métricas a archivo"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"grafana_metrics_export_{timestamp}.json"

            import json

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.get_metrics_summary(), f, indent=2, ensure_ascii=False)

            self.logger.info(f"📁 Métricas exportadas a: {filename}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error exportando métricas: {e}")
            return False
