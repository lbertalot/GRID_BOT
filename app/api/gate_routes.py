"""Read-only live gate status (ADR-007 / RFC-004).

Consumed by the go-live dashboard to render the signoff state. Read-only by
design: there is no endpoint to sign, approve or bypass the gate — signing is a
human act on a file outside the application.

Auth is applied where the router is mounted (``app/main.py``): the detail below
names people and enumerates which controls are still pending, so it is not
public. The unauthenticated mode badge lives in ``/health/trading-mode``.
"""

from datetime import datetime

from fastapi import APIRouter

from app.core.live_gate import get_live_gate_status

router = APIRouter(prefix="/api/gates", tags=["gates"])


@router.get("/live-status")
async def live_gate_status():
    """Dual signoff status. No secrets, no absolute paths, no env values."""
    return {
        "timestamp": datetime.now().isoformat(),
        "gate": get_live_gate_status(),
    }
