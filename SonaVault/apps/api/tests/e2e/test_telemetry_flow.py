import pytest
from httpx import ASGITransport, AsyncClient

from sonavault.main import create_app

pytestmark = pytest.mark.asyncio


async def test_get_gb10_telemetry():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/telemetry/gb10")
        assert resp.status_code == 200
        data = resp.json()
        assert "unified_memory" in data
        assert "gpu" in data
        assert "moe" in data
        assert "sidecars" in data
        assert data["unified_memory"]["total_bytes"] > 0
        assert data["gpu"]["device_name"] == "NVIDIA GB10"
        assert data["gpu"]["unified_memory_mode"] is True


async def test_get_health_summary():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/telemetry/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "critical")
        assert data["memory_pressure_level"] in ("normal", "warning", "critical")
        assert data["sidecars_total"] >= 4
