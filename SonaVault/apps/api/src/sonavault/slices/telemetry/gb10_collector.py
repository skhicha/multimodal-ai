"""Collector for NVIDIA DGX Spark GB10 Hardware Telemetry & Prometheus Metrics.

Monitors Grace ARM64 + Blackwell sm_121 Unified LPDDR5X memory,
GPU compute cores, Qwen3-30B-A3B-NVFP4 MoE routing stats, and sidecar health.
"""

import os
import platform
import subprocess
import time
from datetime import UTC, datetime

import httpx
import psutil
from prometheus_client import Gauge

from sonavault.config import get_settings
from sonavault.slices.telemetry.schemas import (
    GB10TelemetryResponse,
    GpuTelemetry,
    HealthSummaryResponse,
    MoETelemetry,
    SidecarStatus,
    UnifiedMemoryTelemetry,
)

# Prometheus Gauges
GAUGE_MEM_TOTAL = Gauge("gb10_unified_memory_total_bytes", "Total Unified LPDDR5X memory in bytes")
GAUGE_MEM_USED = Gauge("gb10_unified_memory_used_bytes", "Used Unified LPDDR5X memory in bytes")
GAUGE_MEM_AVAIL = Gauge(
    "gb10_unified_memory_available_bytes", "Available Unified LPDDR5X memory in bytes"
)
GAUGE_GPU_UTIL = Gauge("gb10_gpu_utilization_ratio", "Blackwell GPU utilization ratio (0.0 to 1.0)")
GAUGE_GPU_TEMP = Gauge("gb10_gpu_temperature_celsius", "Blackwell GPU core temperature in Celsius")
GAUGE_MOE_RUNNING = Gauge("gb10_moe_running_requests", "Active concurrent requests in vLLM MoE")
GAUGE_MOE_CACHE = Gauge("gb10_moe_gpu_cache_usage_ratio", "vLLM KV-cache memory usage ratio")
GAUGE_SIDECAR_HEALTH = Gauge(
    "sonavault_sidecar_health", "Health status of sidecar (1=healthy, 0=down)", ["service"]
)
GAUGE_SIDECAR_LATENCY = Gauge(
    "sonavault_sidecar_latency_seconds", "Sidecar health check response latency", ["service"]
)


def get_unified_memory_info() -> UnifiedMemoryTelemetry:
    vm = psutil.virtual_memory()
    total = vm.total
    avail = vm.available
    used = total - avail
    pct = round((used / total) * 100, 2) if total > 0 else 0.0

    GAUGE_MEM_TOTAL.set(total)
    GAUGE_MEM_USED.set(used)
    GAUGE_MEM_AVAIL.set(avail)

    return UnifiedMemoryTelemetry(
        total_bytes=total,
        used_bytes=used,
        available_bytes=avail,
        utilization_percent=pct,
        total_gib=round(total / (1024**3), 2),
        used_gib=round(used / (1024**3), 2),
    )


def get_gpu_telemetry() -> GpuTelemetry:
    device_name = "NVIDIA GB10"
    util_pct = 0.0
    temp_c = 42.0
    power_w = None

    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            timeout=2,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        if len(parts) >= 3:
            device_name = parts[0]
            try:
                util_pct = float(parts[1])
            except ValueError:
                util_pct = 0.0
            try:
                temp_c = float(parts[2])
            except ValueError:
                temp_c = 40.0
            if len(parts) >= 4:
                try:
                    power_w = float(parts[3])
                except ValueError:
                    power_w = None
    except Exception:
        pass

    GAUGE_GPU_UTIL.set(util_pct / 100.0)
    GAUGE_GPU_TEMP.set(temp_c)

    return GpuTelemetry(
        device_name=device_name,
        utilization_percent=util_pct,
        temperature_celsius=temp_c,
        power_watts=power_w,
        unified_memory_mode=True,
        architecture="Blackwell sm_121",
    )


async def check_sidecar_health(name: str, url: str, path: str = "/healthz") -> SidecarStatus:
    start = time.perf_counter()
    healthy = False
    latency_ms = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{url.rstrip('/')}{path}")
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            healthy = resp.status_code == 200
    except Exception:
        healthy = False

    GAUGE_SIDECAR_HEALTH.labels(service=name).set(1.0 if healthy else 0.0)
    if latency_ms is not None:
        GAUGE_SIDECAR_LATENCY.labels(service=name).set(latency_ms / 1000.0)

    return SidecarStatus(
        name=name,
        url=url,
        healthy=healthy,
        latency_ms=latency_ms,
        last_checked=datetime.now(UTC),
    )


async def get_moe_telemetry() -> MoETelemetry:
    settings = get_settings()
    vllm_url = settings.vllm_base_url
    running_reqs = 0
    waiting_reqs = 0
    cache_usage = 0.0
    throughput = 0.0

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{vllm_url}/metrics")
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    if line.startswith("vllm:num_requests_running"):
                        running_reqs = int(float(line.split()[-1]))
                    elif line.startswith("vllm:num_requests_waiting"):
                        waiting_reqs = int(float(line.split()[-1]))
                    elif line.startswith("vllm:gpu_cache_usage_factor"):
                        cache_usage = float(line.split()[-1]) * 100
                    elif line.startswith("vllm:avg_generation_throughput_tok_per_s"):
                        throughput = float(line.split()[-1])
    except Exception:
        pass

    GAUGE_MOE_RUNNING.set(running_reqs)
    GAUGE_MOE_CACHE.set(cache_usage / 100.0)

    return MoETelemetry(
        model_id=settings.vllm_model_id,
        running_requests=running_reqs,
        waiting_requests=waiting_reqs,
        gpu_cache_usage_percent=round(cache_usage, 1),
        generation_throughput_tok_s=round(throughput, 1),
        quantization="NVFP4",
    )


async def collect_full_telemetry() -> GB10TelemetryResponse:
    settings = get_settings()
    mem = get_unified_memory_info()
    gpu = get_gpu_telemetry()
    moe = await get_moe_telemetry()

    sidecars = [
        await check_sidecar_health("speech-audio-gpu", settings.speech_sidecar_url, "/healthz"),
        await check_sidecar_health("nlp-retrieval-gpu", settings.nlp_sidecar_url, "/healthz"),
        await check_sidecar_health("vllm-moe-gpu", settings.vllm_base_url, "/health"),
        await check_sidecar_health("qdrant-vector", settings.qdrant_url, "/healthz"),
    ]

    return GB10TelemetryResponse(
        timestamp=datetime.now(UTC),
        hostname=platform.node(),
        platform=f"{platform.system()} {platform.machine()} (ARM64 Spark)",
        unified_memory=mem,
        gpu=gpu,
        moe=moe,
        pipeline_jobs_running=0,
        sidecars=sidecars,
    )


async def get_health_summary() -> HealthSummaryResponse:
    telemetry = await collect_full_telemetry()
    healthy_count = sum(1 for s in telemetry.sidecars if s.healthy)
    total_count = len(telemetry.sidecars)

    mem_pct = telemetry.unified_memory.utilization_percent
    if mem_pct > 88.0:
        pressure = "critical"
    elif mem_pct > 75.0:
        pressure = "warning"
    else:
        pressure = "normal"

    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else 1.0

    if healthy_count == total_count and pressure != "critical":
        overall = "healthy"
    elif healthy_count >= 2:
        overall = "degraded"
    else:
        overall = "critical"

    return HealthSummaryResponse(
        status=overall,
        system_load_1m=round(load_1m, 2),
        memory_pressure_level=pressure,
        sidecars_healthy=healthy_count,
        sidecars_total=total_count,
        details=telemetry.sidecars,
    )
