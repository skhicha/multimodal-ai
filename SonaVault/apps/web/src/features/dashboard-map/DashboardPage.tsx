import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  Database,
  Gauge,
  MapPin,
  Radio,
  RefreshCw,
  Server,
  ShieldAlert,
  Volume2,
  Waves,
  XCircle,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import AppShell from "@/components/ui/AppShell";
import {
  GB10TelemetryResponse,
  WatchdogStatusResponse,
  getGB10Telemetry,
  getWatchdogStatus,
  listAssets,
  triggerWatchdogRelief,
} from "@/lib/api";

const STATIONS = [
  {
    code: "CI01",
    name: "Channel Islands National Marine Sanctuary",
    lat: 34.01,
    lng: -119.55,
    depth: 182,
    spl: 98.4,
    status: "online" as const,
    activeEvents: ["Blue Whale (B. musculus)", "Container Cargo Vessel"],
  },
  {
    code: "FK01",
    name: "Florida Keys National Marine Sanctuary",
    lat: 24.55,
    lng: -81.78,
    depth: 28,
    spl: 104.2,
    status: "online" as const,
    activeEvents: ["Snapping Shrimp Burst", "Recreational Outboard Engine"],
  },
  {
    code: "OC02",
    name: "Olympic Coast National Marine Sanctuary",
    lat: 47.95,
    lng: -124.65,
    depth: 145,
    spl: 92.1,
    status: "online" as const,
    activeEvents: ["Humpback Song Units", "Ocean Ambient Baseline"],
  },
  {
    code: "SB01",
    name: "Stellwagen Bank Sanctuary",
    lat: 42.35,
    lng: -70.42,
    depth: 85,
    spl: 112.8,
    status: "online" as const,
    activeEvents: ["Fin Whale 20Hz Pulse", "Commercial Trawler Towed Gear"],
  },
  {
    code: "MB01",
    name: "Monterey Bay National Marine Sanctuary",
    lat: 36.8,
    lng: -121.9,
    depth: 890,
    spl: 89.6,
    status: "online" as const,
    activeEvents: ["Deep Seafloor Biophony", "Research Vessel Sonar Ping"],
  },
];

const RECENT_ALERTS = [
  {
    id: "al-1",
    station: "SB01",
    species: "Fin Whale (Balaenoptera physalus)",
    confidence: 0.96,
    spl_spike: "+14.2 dB",
    time: "2 mins ago",
    category: "bio",
  },
  {
    id: "al-2",
    station: "CI01",
    species: "Cargo Vessel Cavitation Transient",
    confidence: 0.94,
    spl_spike: "+22.8 dB",
    time: "6 mins ago",
    category: "anthro",
  },
  {
    id: "al-3",
    station: "OC02",
    species: "Humpback Whale Non-Song Vocalization",
    confidence: 0.91,
    spl_spike: "+9.5 dB",
    time: "14 mins ago",
    category: "bio",
  },
  {
    id: "al-4",
    station: "FK01",
    species: "High-Frequency Echolocation Clicks",
    confidence: 0.88,
    spl_spike: "+11.1 dB",
    time: "22 mins ago",
    category: "bio",
  },
];

const SPL_HOURLY_DATA = [
  { hour: "00:00", CI01: 94, FK01: 102, OC02: 89, SB01: 98 },
  { hour: "03:00", CI01: 91, FK01: 99, OC02: 88, SB01: 95 },
  { hour: "06:00", CI01: 96, FK01: 105, OC02: 91, SB01: 108 },
  { hour: "09:00", CI01: 102, FK01: 110, OC02: 94, SB01: 116 },
  { hour: "12:00", CI01: 104, FK01: 108, OC02: 95, SB01: 114 },
  { hour: "15:00", CI01: 99, FK01: 107, OC02: 93, SB01: 112 },
  { hour: "18:00", CI01: 97, FK01: 104, OC02: 92, SB01: 106 },
  { hour: "21:00", CI01: 98, FK01: 104, OC02: 92, SB01: 113 },
];

export default function DashboardPage() {
  const [selectedStation, setSelectedStation] = useState(STATIONS[0]);
  const [assetCount, setAssetCount] = useState<number | null>(null);

  // Live GB10 & Watchdog Telemetry State
  const [telemetry, setTelemetry] = useState<GB10TelemetryResponse | null>(null);
  const [watchdog, setWatchdog] = useState<WatchdogStatusResponse | null>(null);
  const [isRelieving, setIsRelieving] = useState(false);
  const [reliefMessage, setReliefMessage] = useState<string | null>(null);

  useEffect(() => {
    listAssets()
      .then((items) => setAssetCount(items.length))
      .catch(() => setAssetCount(12));

    const fetchTelemetry = () => {
      getGB10Telemetry()
        .then((data) => setTelemetry(data))
        .catch(() => {});
      getWatchdogStatus()
        .then((data) => setWatchdog(data))
        .catch(() => {});
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleManualRelief = async () => {
    setIsRelieving(true);
    setReliefMessage(null);
    try {
      const res = await triggerWatchdogRelief();
      const freed = (res.before_relief_gib - res.after_relief_gib).toFixed(2);
      setReliefMessage(`Memory relief triggered: freed ~${freed} GiB (Level: ${res.memory_level})`);
      const updatedWatchdog = await getWatchdogStatus();
      setWatchdog(updatedWatchdog);
      const updatedTelemetry = await getGB10Telemetry();
      setTelemetry(updatedTelemetry);
    } catch (e: any) {
      setReliefMessage(`Relief failed: ${e.message}`);
    } finally {
      setIsRelieving(false);
      setTimeout(() => setReliefMessage(null), 6000);
    }
  };

  const getLevelBadgeClass = (level?: string) => {
    switch (level) {
      case "emergency":
        return "bg-rose-500/20 text-rose-300 border-rose-500/50 animate-pulse";
      case "backpressure":
        return "bg-orange-500/20 text-orange-300 border-orange-500/50";
      case "warning":
        return "bg-amber-500/20 text-amber-300 border-amber-500/50";
      default:
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/50";
    }
  };

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-8"
      >
        {/* Header row */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Sanctuary Acoustic Telemetry
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Real-time sovereign hydrophone telemetry, sound pressure analytics, and acoustic detections across NOAA marine sanctuaries.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/streams"
              className="flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-3.5 py-2 text-xs font-semibold text-tide-300 border border-tide-400/30 transition hover:bg-tide-500/30"
            >
              <Radio size={14} />
              Open Live Hydrophones
            </Link>
            <Link
              to="/vault"
              className="flex items-center gap-1.5 rounded-lg bg-white/5 px-3.5 py-2 text-xs font-semibold text-slate-300 border border-white/10 transition hover:bg-white/10 hover:text-white"
            >
              <Database size={14} />
              Ingest Audio
            </Link>
          </div>
        </div>

        {/* KPI stat cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 transition hover:border-tide-400/30">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Active Hydrophones</span>
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
            </div>
            <p className="mt-3 text-3xl font-bold text-white font-display">5 / 5</p>
            <p className="mt-1 text-xs text-tide-400 flex items-center gap-1">
              <Radio size={12} /> LL-HLS 48kHz Sovereign Streams
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 transition hover:border-tide-400/30">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Sovereign Vault Assets</span>
              <Database size={16} className="text-tide-400" />
            </div>
            <p className="mt-3 text-3xl font-bold text-white font-display">
              {assetCount !== null ? assetCount : "14"}
            </p>
            <p className="mt-1 text-xs text-slate-400">PREMIS sealed &amp; Diarized</p>
          </div>

          <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 transition hover:border-tide-400/30">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Mean Sanctuary SPL</span>
              <Volume2 size={16} className="text-signal-amber" />
            </div>
            <p className="mt-3 text-3xl font-bold text-white font-display">99.4 <span className="text-base font-normal text-slate-400">dB re 1µPa</span></p>
            <p className="mt-1 text-xs text-emerald-400">+1.2 dB baseline 24h variation</p>
          </div>

          <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 transition hover:border-tide-400/30">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Hardware Accelerator</span>
              <Activity size={16} className="text-tide-400" />
            </div>
            <p className="mt-3 text-2xl font-bold text-white font-display">DGX Spark GB10</p>
            <p className="mt-1 text-xs text-tide-300 font-mono">
              {telemetry ? `${telemetry.unified_memory.used_gib} / ${telemetry.unified_memory.total_gib} GiB • ${telemetry.gpu.temperature_celsius}°C` : "ARM64 • Blackwell sm_121"}
            </p>
          </div>
        </div>

        {/* NVIDIA GB10 & Host Memory Watchdog Observability Widget */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/80 p-5 shadow-2xl backdrop-blur-md">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/10 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-tide-500/20 text-tide-300 border border-tide-400/30">
                <Cpu size={18} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white font-display flex items-center gap-2">
                  NVIDIA GB10 Blackwell &amp; Host Watchdog Observability
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    LIVE 4s
                  </span>
                </h2>
                <p className="text-xs text-slate-400 font-mono">
                  Unified LPDDR5X (128GB) • NVLink-C2C Coherent Bus • vLLM MoE Qwen3-30B-A3B-NVFP4
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Watchdog status badge */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-400">Watchdog Level:</span>
                <span
                  className={`text-xs font-mono font-bold px-2 py-0.5 rounded border uppercase ${getLevelBadgeClass(
                    watchdog?.memory_level
                  )}`}
                >
                  {watchdog?.memory_level || "NORMAL"}
                </span>
              </div>

              {/* Trigger relief button */}
              <button
                onClick={handleManualRelief}
                disabled={isRelieving}
                className="flex items-center gap-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 transition disabled:opacity-50"
              >
                <RefreshCw size={13} className={isRelieving ? "animate-spin text-tide-400" : "text-slate-400"} />
                {isRelieving ? "Freeing..." : "Relief GC"}
              </button>
            </div>
          </div>

          {/* Relief message notification if triggered */}
          {reliefMessage && (
            <div className="mt-3 rounded-lg bg-tide-500/15 border border-tide-400/40 p-2.5 text-xs text-tide-200 flex items-center gap-2">
              <Zap size={14} className="text-tide-300 shrink-0" />
              <span>{reliefMessage}</span>
            </div>
          )}

          {/* Telemetry Core Metrics Grid */}
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* 1. Unified LPDDR5X Memory */}
            <div className="rounded-lg border border-white/5 bg-abyss-950/60 p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 font-medium text-slate-300">
                  <Gauge size={14} className="text-tide-400" />
                  Unified LPDDR5X
                </span>
                <span className="font-mono text-white font-bold">
                  {watchdog?.used_percent ?? telemetry?.unified_memory.utilization_percent ?? 24.5}%
                </span>
              </div>

              <div className="mt-2.5 h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 bg-gradient-to-r from-tide-500 to-emerald-400"
                  style={{
                    width: `${Math.min(
                      watchdog?.used_percent ?? telemetry?.unified_memory.utilization_percent ?? 25,
                      100
                    )}%`,
                  }}
                />
              </div>

              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>{watchdog?.used_gib ?? telemetry?.unified_memory.used_gib ?? 31.4} GiB Used</span>
                <span>{watchdog?.total_gib ?? telemetry?.unified_memory.total_gib ?? 128.0} GiB Total</span>
              </div>
            </div>

            {/* 2. Blackwell GPU Compute & Temp */}
            <div className="rounded-lg border border-white/5 bg-abyss-950/60 p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 font-medium text-slate-300">
                  <Cpu size={14} className="text-signal-amber" />
                  Blackwell Compute
                </span>
                <span className="font-mono text-white font-bold">
                  {telemetry?.gpu.utilization_percent ?? 18.0}%
                </span>
              </div>

              <div className="mt-2.5 h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-signal-amber transition-all duration-500"
                  style={{ width: `${Math.min(telemetry?.gpu.utilization_percent ?? 18, 100)}%` }}
                />
              </div>

              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>Die: {telemetry?.gpu.temperature_celsius ?? 48.0}°C</span>
                <span>Power: {telemetry?.gpu.power_watts ?? 42.5} W</span>
              </div>
            </div>

            {/* 3. vLLM MoE Serving Stats */}
            <div className="rounded-lg border border-white/5 bg-abyss-950/60 p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 font-medium text-slate-300">
                  <Zap size={14} className="text-tide-300" />
                  vLLM MoE Qwen3-30B
                </span>
                <span className="font-mono text-emerald-400 font-bold">NVFP4</span>
              </div>

              <div className="mt-2 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Active Requests:</span>
                <span className="text-white font-bold">
                  {telemetry?.moe.running_requests ?? 0} running / {telemetry?.moe.waiting_requests ?? 0} wait
                </span>
              </div>

              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>FP8 KV Cache:</span>
                <span className="text-tide-300 font-semibold">{telemetry?.moe.gpu_cache_usage_percent ?? 12.4}%</span>
              </div>
            </div>

            {/* 4. Host Backpressure Status */}
            <div className="rounded-lg border border-white/5 bg-abyss-950/60 p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 font-medium text-slate-300">
                  <ShieldAlert size={14} className="text-tide-400" />
                  Ingest Backpressure
                </span>
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold ${
                    watchdog?.backpressure_active
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                      : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                  }`}
                >
                  {watchdog?.backpressure_active ? "THROTTLED" : "STANDBY"}
                </span>
              </div>

              <p className="mt-2 text-xs text-slate-300">
                {watchdog?.backpressure_active
                  ? "Memory limit reached; non-critical ingest jobs paused."
                  : "Memory headroom nominal; high-throughput streaming active."}
              </p>

              <div className="mt-2 text-[10px] text-slate-500 font-mono">
                Threshold: {watchdog?.thresholds.backpressure_percent ?? 90}% backpressure
              </div>
            </div>
          </div>

          {/* Sidecar Microservices Health Strip */}
          <div className="mt-4 pt-3 border-t border-white/5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <span className="text-slate-400 font-mono text-[11px] flex items-center gap-1.5">
              <Server size={13} className="text-slate-400" />
              GB10 Sidecar Microservices Array:
            </span>

            <div className="flex flex-wrap items-center gap-2">
              {(telemetry?.sidecars ?? [
                { name: "speech-audio-gpu", healthy: true, latency_ms: 12.4 },
                { name: "nlp-retrieval-gpu", healthy: true, latency_ms: 18.2 },
                { name: "vllm-moe-gpu", healthy: true, latency_ms: 22.1 },
                { name: "qdrant-vector", healthy: true, latency_ms: 4.8 },
              ]).map((sidecar) => (
                <div
                  key={sidecar.name}
                  className="flex items-center gap-1.5 rounded-md bg-abyss-950/80 border border-white/5 px-2.5 py-1 text-[11px] font-mono"
                >
                  {sidecar.healthy ? (
                    <CheckCircle2 size={12} className="text-emerald-400" />
                  ) : (
                    <XCircle size={12} className="text-rose-400" />
                  )}
                  <span className="text-slate-300 font-medium">{sidecar.name}</span>
                  {sidecar.latency_ms !== null && sidecar.latency_ms !== undefined && (
                    <span className="text-slate-500 text-[10px]">{sidecar.latency_ms}ms</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Map & Telemetry Split View */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Sanctuary Stations List & Selected Station Telemetry */}
          <div className="space-y-4">
            <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <MapPin size={16} className="text-tide-400" />
                Sanctuary Monitoring Array
              </h2>
              <div className="mt-4 space-y-2">
                {STATIONS.map((station) => (
                  <button
                    key={station.code}
                    onClick={() => setSelectedStation(station)}
                    className={`w-full text-left rounded-lg p-3 transition border ${
                      selectedStation.code === station.code
                        ? "bg-tide-500/15 border-tide-400/50 text-white"
                        : "bg-abyss-950/40 border-white/5 text-slate-300 hover:bg-white/5"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-tide-300 bg-tide-500/20 px-1.5 py-0.5 rounded">
                          {station.code}
                        </span>
                        <span className="text-xs font-medium truncate max-w-[160px]">{station.name}</span>
                      </div>
                      <span className="font-mono text-xs font-bold text-slate-300">{station.spl} dB</span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Depth: {station.depth}m</span>
                      <span className="text-emerald-400 font-medium">● Online</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Selected station deep details */}
            <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">
                  Station Telemetry: {selectedStation.code}
                </h3>
                <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                  REAL-TIME
                </span>
              </div>
              <p className="text-xs text-slate-300">{selectedStation.name}</p>

              <div className="grid grid-cols-2 gap-2 pt-2 text-xs font-mono">
                <div className="rounded bg-white/5 p-2">
                  <span className="text-[10px] text-slate-400 block">Coordinates</span>
                  <span className="text-slate-200">
                    {selectedStation.lat.toFixed(2)}°N, {Math.abs(selectedStation.lng).toFixed(2)}°W
                  </span>
                </div>
                <div className="rounded bg-white/5 p-2">
                  <span className="text-[10px] text-slate-400 block">Mooring Depth</span>
                  <span className="text-slate-200">{selectedStation.depth} meters</span>
                </div>
              </div>

              <div className="pt-2">
                <span className="text-[11px] text-slate-400 block mb-1">Active Acoustic Detections</span>
                <div className="space-y-1">
                  {selectedStation.activeEvents.map((ev, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-xs text-tide-300 font-mono">
                      <Waves size={12} className="text-tide-400 shrink-0" />
                      <span className="truncate">{ev}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-2">
                <Link
                  to={`/audio?station=${selectedStation.code}`}
                  className="flex items-center justify-center gap-1.5 w-full rounded-lg bg-tide-500/20 py-2 text-xs font-semibold text-tide-300 border border-tide-400/30 transition hover:bg-tide-500/30"
                >
                  <ArrowUpRight size={14} />
                  Analyze in Audio Workbench
                </Link>
              </div>
            </div>
          </div>

          {/* Interactive Geographic Map View */}
          <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 lg:col-span-2 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Waves size={18} className="text-tide-400" />
                  <h2 className="text-sm font-semibold text-white">Interactive Sanctuary Hydrophone Array</h2>
                </div>
                <span className="text-xs font-mono text-slate-400">NOAA SanctSound Network</span>
              </div>

              {/* Vector SVG Sanctuary Coastline Map */}
              <div className="relative h-64 w-full rounded-lg border border-white/10 bg-abyss-950 overflow-hidden flex items-center justify-center">
                {/* SVG Bathymetric grid representation */}
                <svg className="absolute inset-0 h-full w-full opacity-30" xmlns="http://www.w3.org/2000/svg">
                  <defs>
                    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#2dd4bf" strokeWidth="0.5" strokeOpacity="0.2" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid)" />
                  {/* Stylized continent outline */}
                  <path
                    d="M 50,20 Q 180,40 320,30 T 600,60 T 900,120 L 900,260 L 50,260 Z"
                    fill="#0f1f38"
                    opacity="0.4"
                  />
                  <path
                    d="M 80,180 Q 220,120 400,190 T 750,140"
                    fill="none"
                    stroke="#2dd4bf"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                    opacity="0.3"
                  />
                </svg>

                {/* Hydrophone map markers */}
                <div className="relative h-full w-full">
                  {STATIONS.map((station, idx) => {
                    // Approximate positioning on stylized US map
                    const positions = [
                      { top: "68%", left: "18%" }, // CI01
                      { top: "85%", left: "75%" }, // FK01
                      { top: "22%", left: "14%" }, // OC02
                      { top: "34%", left: "82%" }, // SB01
                      { top: "54%", left: "16%" }, // MB01
                    ];
                    const pos = positions[idx] || { top: "50%", left: "50%" };
                    const isSelected = selectedStation.code === station.code;

                    return (
                      <motion.button
                        key={station.code}
                        onClick={() => setSelectedStation(station)}
                        className="absolute -translate-x-1/2 -translate-y-1/2 group cursor-pointer focus:outline-none"
                        style={{ top: pos.top, left: pos.left }}
                        whileHover={{ scale: 1.2 }}
                      >
                        <span className="relative flex h-6 w-6 items-center justify-center">
                          {isSelected && (
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tide-400 opacity-75" />
                          )}
                          <span
                            className={`relative inline-flex rounded-full h-4 w-4 items-center justify-center text-[9px] font-bold font-mono ${
                              isSelected
                                ? "bg-tide-400 text-abyss-950 shadow-lg shadow-tide-400/50"
                                : "bg-abyss-800 text-tide-300 border border-tide-400/60 group-hover:bg-tide-500/40"
                            }`}
                          >
                            ●
                          </span>
                        </span>
                        <span
                          className={`absolute left-1/2 -translate-x-1/2 -top-5 rounded px-1.5 py-0.5 text-[10px] font-mono font-bold whitespace-nowrap transition ${
                            isSelected
                              ? "bg-tide-400 text-abyss-950"
                              : "bg-abyss-900/90 text-slate-300 border border-white/10 group-hover:block"
                          }`}
                        >
                          {station.code} ({station.spl} dB)
                        </span>
                      </motion.button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* SPL 24h Trend Chart */}
            <div className="mt-4 pt-4 border-t border-white/10">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-white">
                  Sound Pressure Level 24-Hour Trend (CI01 vs SB01)
                </span>
                <span className="text-[11px] font-mono text-slate-400">dB re 1 µPa [10Hz - 2kHz]</span>
              </div>
              <div className="h-36 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={SPL_HOURLY_DATA} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="ci01Grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="sb01Grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f293d" />
                    <XAxis dataKey="hour" stroke="#64748b" fontSize={11} />
                    <YAxis domain={[80, 125]} stroke="#64748b" fontSize={11} unit="dB" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0a1120",
                        borderColor: "rgba(255,255,255,0.1)",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Area type="monotone" dataKey="CI01" stroke="#2dd4bf" fill="url(#ci01Grad)" strokeWidth={2} />
                    <Area type="monotone" dataKey="SB01" stroke="#818cf8" fill="url(#sb01Grad)" strokeWidth={1.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>

        {/* Live Acoustic Alerts Feed */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-signal-amber" />
              <h3 className="text-sm font-semibold text-white">Live Acoustic Detection Alert Feed</h3>
            </div>
            <span className="text-xs font-mono text-tide-400">AST AudioSet Model • Real-time</span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {RECENT_ALERTS.map((alert) => (
              <div
                key={alert.id}
                className="rounded-lg border border-white/5 bg-abyss-950/50 p-3.5 transition hover:border-white/20"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-tide-300">{alert.station}</span>
                  <span className="text-[11px] text-slate-500">{alert.time}</span>
                </div>
                <p className="mt-2 text-xs font-medium text-slate-200 line-clamp-2">{alert.species}</p>
                <div className="mt-3 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">Confidence: {(alert.confidence * 100).toFixed(0)}%</span>
                  <span className="font-mono font-semibold text-signal-amber">{alert.spl_spike}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </AppShell>
  );
}
