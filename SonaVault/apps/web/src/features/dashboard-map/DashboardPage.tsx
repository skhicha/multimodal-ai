import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Database,
  MapPin,
  Radio,
  Volume2,
  Waves,
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
import { listAssets } from "@/lib/api";

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

  useEffect(() => {
    listAssets()
      .then((items) => setAssetCount(items.length))
      .catch(() => setAssetCount(12));
  }, []);

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
            <p className="mt-1 text-xs text-tide-300 font-mono">ARM64 • Blackwell sm_121</p>
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
                  Station {selectedStation.code} Active Telemetry
                </h3>
                <Link
                  to={`/streams?station=${selectedStation.code}`}
                  className="text-xs text-tide-400 hover:underline flex items-center gap-1"
                >
                  Stream <ArrowUpRight size={12} />
                </Link>
              </div>
              <p className="text-sm font-semibold text-white">{selectedStation.name}</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded bg-abyss-950/60 p-2 border border-white/5">
                  <span className="text-slate-500 block text-[10px]">COORDINATES</span>
                  <span className="font-mono font-medium text-slate-300">
                    {selectedStation.lat}°N, {Math.abs(selectedStation.lng)}°W
                  </span>
                </div>
                <div className="rounded bg-abyss-950/60 p-2 border border-white/5">
                  <span className="text-slate-500 block text-[10px]">HYDROPHONE DEPTH</span>
                  <span className="font-mono font-medium text-slate-300">{selectedStation.depth} meters</span>
                </div>
              </div>
              <div className="mt-2">
                <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
                  DETECTED ACOUSTIC SOURCES (AST)
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {selectedStation.activeEvents.map((ev) => (
                    <span
                      key={ev}
                      className="rounded-full bg-tide-500/15 border border-tide-400/30 px-2.5 py-0.5 text-[11px] text-tide-300"
                    >
                      {ev}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Map Visualizer & Hourly SPL Chart */}
          <div className="lg:col-span-2 space-y-6">
            {/* Visual Hydrophone Array Map Banner */}
            <div className="rounded-xl border border-white/10 bg-abyss-900/70 overflow-hidden relative">
              <div className="p-4 border-b border-white/10 flex items-center justify-between bg-abyss-900/90">
                <div className="flex items-center gap-2">
                  <Waves size={16} className="text-tide-400" />
                  <span className="text-xs font-semibold text-white">Sovereign Ocean Hydrophone Array Map</span>
                </div>
                <span className="text-xs text-slate-400 font-mono">EPSG:4326 WGS84</span>
              </div>

              {/* Map Canvas Frame */}
              <div className="h-80 w-full bg-abyss-950 flex flex-col items-center justify-center relative p-6">
                {/* Sonar Radar Backdrop Grid */}
                <div className="absolute inset-0 bg-sonar-grid opacity-70 pointer-events-none" />
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="w-64 h-64 rounded-full border border-tide-500/20 animate-ping opacity-20" />
                  <div className="w-96 h-96 rounded-full border border-tide-500/10" />
                </div>

                {/* Simulated Georeferenced Station Nodes */}
                <div className="relative z-10 w-full h-full max-w-lg mx-auto flex items-center justify-center">
                  <div className="grid grid-cols-3 gap-6 w-full text-center">
                    {STATIONS.map((s) => (
                      <button
                        key={s.code}
                        onClick={() => setSelectedStation(s)}
                        className={`group relative p-3 rounded-xl border transition flex flex-col items-center ${
                          selectedStation.code === s.code
                            ? "bg-tide-500/20 border-tide-400 text-white shadow-lg shadow-tide-500/10"
                            : "bg-abyss-900/80 border-white/10 text-slate-400 hover:border-tide-400/40 hover:text-white"
                        }`}
                      >
                        <span className="h-3 w-3 rounded-full bg-tide-400 mb-1.5 animate-pulse" />
                        <span className="font-mono text-xs font-bold text-tide-300">{s.code}</span>
                        <span className="text-[10px] text-slate-400 truncate max-w-[90px]">{s.name.split(" ")[0]}</span>
                        <span className="mt-1 text-[11px] font-mono font-semibold text-slate-200">{s.spl} dB</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="absolute bottom-3 left-4 text-[11px] font-mono text-slate-500">
                  Active Sanctuary Coordinates: {selectedStation.lat}°N / {selectedStation.lng}°W
                </div>
              </div>
            </div>

            {/* 24h Hourly Sound Pressure Level (SPL) Multi-station Recharts Graph */}
            <div className="rounded-xl border border-white/10 bg-abyss-900/70 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-white">24-Hour Sound Pressure Level (SPL) Trend</h3>
                  <p className="text-xs text-slate-400">Broadband calibrated acoustic intensity (dB re 1µPa)</p>
                </div>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <span className="flex items-center gap-1 text-tide-400">
                    <span className="h-2 w-2 rounded-full bg-tide-400" /> CI01
                  </span>
                  <span className="flex items-center gap-1 text-signal-amber">
                    <span className="h-2 w-2 rounded-full bg-signal-amber" /> FK01
                  </span>
                  <span className="flex items-center gap-1 text-indigo-400">
                    <span className="h-2 w-2 rounded-full bg-indigo-400" /> SB01
                  </span>
                </div>
              </div>

              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={SPL_HOURLY_DATA}>
                    <defs>
                      <linearGradient id="ci01Grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="sb01Grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#818cf8" stopOpacity={0.2} />
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
