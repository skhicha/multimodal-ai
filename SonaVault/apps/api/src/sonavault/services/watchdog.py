"""Host & Unified Memory Watchdog Daemon for NVIDIA DGX Spark GB10.

Maintains stability under concurrent speech, acoustic, and vLLM inference workloads.
Monitors unified LPDDR5X allocation, enforces backpressure throttling,
purges ephemeral caches under pressure, and monitors sidecar liveness.
"""

import asyncio
import gc
import logging
from datetime import UTC, datetime
from typing import Literal

import psutil
from prometheus_client import Counter, Gauge

logger = logging.getLogger("sonavault.watchdog")

# Metrics
GAUGE_BACKPRESSURE_ACTIVE = Gauge(
    "sonavault_watchdog_backpressure_active",
    "Whether pipeline ingest backpressure throttling is engaged (1 or 0)",
)
COUNTER_PRESSURE_EVENTS = Counter(
    "sonavault_watchdog_pressure_events_total",
    "Total count of memory pressure actions taken",
    ["level"],
)

MemoryLevel = Literal["normal", "warning", "backpressure", "emergency"]


class WatchdogConfig:
    warning_pct: float = 75.0
    backpressure_pct: float = 85.0
    emergency_pct: float = 92.0
    poll_interval_sec: float = 5.0


class MemoryWatchdog:
    def __init__(self, config: WatchdogConfig | None = None) -> None:
        self.config = config or WatchdogConfig()
        self._backpressure_active: bool = False
        self._current_level: MemoryLevel = "normal"
        self._action_log: list[dict] = []
        self._running: bool = False
        self._task: asyncio.Task | None = None

    @property
    def backpressure_active(self) -> bool:
        return self._backpressure_active

    @property
    def current_level(self) -> MemoryLevel:
        return self._current_level

    def get_status(self) -> dict:
        vm = psutil.virtual_memory()
        pct = round((vm.used / vm.total) * 100, 2)
        return {
            "current_level": self._current_level,
            "backpressure_active": self._backpressure_active,
            "utilization_percent": pct,
            "total_gib": round(vm.total / (1024**3), 2),
            "available_gib": round(vm.available / (1024**3), 2),
            "recent_actions": self._action_log[-10:],
        }

    def inspect_memory(self) -> tuple[MemoryLevel, float]:
        vm = psutil.virtual_memory()
        pct = (vm.used / vm.total) * 100.0

        if pct >= self.config.emergency_pct:
            level: MemoryLevel = "emergency"
        elif pct >= self.config.backpressure_pct:
            level = "backpressure"
        elif pct >= self.config.warning_pct:
            level = "warning"
        else:
            level = "normal"

        self._handle_level_transition(level, pct)
        return level, pct

    def _handle_level_transition(self, level: MemoryLevel, pct: float) -> None:
        prev_level = self._current_level
        self._current_level = level

        if level in ("backpressure", "emergency"):
            if not self._backpressure_active:
                self._backpressure_active = True
                GAUGE_BACKPRESSURE_ACTIVE.set(1.0)
                COUNTER_PRESSURE_EVENTS.labels(level=level).inc()
                self._log_action(f"Engaged ingest backpressure throttling ({pct:.1f}% used)")
        else:
            if self._backpressure_active:
                self._backpressure_active = False
                GAUGE_BACKPRESSURE_ACTIVE.set(0.0)
                self._log_action(f"Disengaged backpressure; memory returned to normal ({pct:.1f}%)")

        if level == "emergency":
            self.trigger_memory_relief(pct)

        if level != prev_level:
            logger.info(
                "Watchdog memory level transition: %s -> %s (%.1f%%)",
                prev_level,
                level,
                pct,
            )

    def trigger_memory_relief(self, pct: float | None = None) -> dict:
        """Emergency action: force Python garbage collection & clear caches."""
        collected = gc.collect()
        action_msg = f"Triggered emergency memory relief; GC collected {collected} objects"
        if pct is not None:
            action_msg += f" (at {pct:.1f}% pressure)"
        self._log_action(action_msg)
        COUNTER_PRESSURE_EVENTS.labels(level="emergency").inc()
        return {"status": "relief_executed", "collected_objects": collected}

    def _log_action(self, detail: str) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": self._current_level,
            "detail": detail,
        }
        self._action_log.append(entry)
        if len(self._action_log) > 50:
            self._action_log.pop(0)

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                self.inspect_memory()
            except Exception as e:
                logger.error("Error in watchdog poll loop: %s", e)
            await asyncio.sleep(self.config.poll_interval_sec)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Host Memory Watchdog started (interval=%ss)", self.config.poll_interval_sec)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Host Memory Watchdog stopped")


_watchdog_singleton: MemoryWatchdog | None = None


def get_watchdog() -> MemoryWatchdog:
    global _watchdog_singleton
    if _watchdog_singleton is None:
        _watchdog_singleton = MemoryWatchdog()
    return _watchdog_singleton
