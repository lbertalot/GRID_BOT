from app.core.celery_app import celery_app
from app.core.distributed_lock import with_distributed_lock
import logging
import asyncio

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
@with_distributed_lock("rebalancing", timeout=600, blocking=False)
def check_and_rebalance(self):
    """
    Verifica y ejecuta rebalanceo automático (llamando al AutoRebalancer).

    Con lock distribuido para prevenir múltiples rebalanceos simultáneos.
    """
    try:
        from app.services.auto_rebalancer import auto_rebalancer

        logger.info("Verificando necesidad de rebalanceo")

        async def _run():
            status = await auto_rebalancer.get_rebalance_status()
            if status.get("assets_needing_rebalance", 0) > 0 and status.get(
                "can_rebalance", False
            ):
                return await auto_rebalancer.check_and_rebalance()
            return {
                "status": "skipped",
                "reason": "no_rebalance_needed",
                "status_snapshot": status,
            }

        result = asyncio.run(_run())
        logger.info(f"Resultado rebalanceo: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"Error en rebalanceo: {e}")
        raise self.retry(countdown=300, max_retries=2)
