from datetime import datetime

from pydantic import BaseModel


class UnifiedMemoryTelemetry(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    utilization_percent: float
    total_gib: float
    used_gib: float


class GpuTelemetry(BaseModel):
    device_name: str
    utilization_percent: float
    temperature_celsius: float
    power_watts: float | None = None
    unified_memory_mode: bool = True
    architecture: str = "Blackwell sm_121"


class MoETelemetry(BaseModel):
    model_id: str
    running_requests: int
    waiting_requests: int
    gpu_cache_usage_percent: float
    generation_throughput_tok_s: float
    quantization: str = "NVFP4"


class SidecarStatus(BaseModel):
    name: str
    url: str
    healthy: bool
    latency_ms: float | None = None
    last_checked: datetime


class GB10TelemetryResponse(BaseModel):
    timestamp: datetime
    hostname: str
    platform: str
    unified_memory: UnifiedMemoryTelemetry
    gpu: GpuTelemetry
    moe: MoETelemetry
    pipeline_jobs_running: int
    sidecars: list[SidecarStatus]


class HealthSummaryResponse(BaseModel):
    status: str  # healthy | degraded | critical
    system_load_1m: float
    memory_pressure_level: str  # normal | warning | critical
    sidecars_healthy: int
    sidecars_total: int
    details: list[SidecarStatus]
