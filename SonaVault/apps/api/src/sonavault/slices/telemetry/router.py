from fastapi import APIRouter

from sonavault.services.watchdog import get_watchdog
from sonavault.slices.telemetry.gb10_collector import (
    collect_full_telemetry,
    get_health_summary,
)
from sonavault.slices.telemetry.schemas import (
    GB10TelemetryResponse,
    HealthSummaryResponse,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.get("/gb10", response_model=GB10TelemetryResponse)
async def get_gb10_telemetry():
    """Returns real-time GB10 unified memory, Blackwell GPU, and MoE telemetry."""
    return await collect_full_telemetry()


@router.get("/health-summary", response_model=HealthSummaryResponse)
async def get_system_health():
    """Returns high-level health summary and sidecar status."""
    return await get_health_summary()


@router.get("/watchdog")
async def get_watchdog_status():
    """Returns current host memory watchdog thresholds, level, and actions."""
    watchdog = get_watchdog()
    return watchdog.get_status()


@router.post("/watchdog/relief")
async def trigger_watchdog_relief():
    """Manually triggers emergency memory relief and garbage collection."""
    watchdog = get_watchdog()
    return watchdog.trigger_memory_relief()
