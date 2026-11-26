import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  FileAudio,
  FileText,
  Filter,
  Plus,
  Search,
  ShieldCheck,
  Upload,
  Waves,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";

import AppShell from "@/components/ui/AppShell";
import { ingestAudioFile, listAssets, type AssetOut } from "@/lib/api";

const MOCK_ASSETS: AssetOut[] = [
  {
    sha256: "b6d8f8a12c4e6f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a",
    asset_type: "audio",
    original_filename: "SanctSound_CI01_02_20241014T120000Z.wav",
    mime_type: "audio/wav",
    size_bytes: 4820000,
    sanctuary_id: "CI01",
    station_code: "CI01",
    latitude: 34.0,
    longitude: -120.0,
    geo_qa_flag: null,
  },
  {
    sha256: "c7e9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9",
    asset_type: "audio",
    original_filename: "SanctSound_SB01_05_FinWhale_Pulse20Hz.flac",
    mime_type: "audio/flac",
    size_bytes: 2560000,
    sanctuary_id: "SB01",
    station_code: "SB01",
    latitude: 42.4,
    longitude: -70.3,
    geo_qa_flag: null,
  },
  {
    sha256: "d8f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
    asset_type: "xml",
    original_filename: "NOAA_SanctSound_Monthly_SPL_Summary_CI01.xml",
    mime_type: "application/xml",
    size_bytes: 128000,
    sanctuary_id: "CI01",
    station_code: "CI01",
    latitude: 34.0,
    longitude: -120.0,
    geo_qa_flag: null,
  },
  {
    sha256: "e9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
    asset_type: "audio",
    original_filename: "FLEURS_MarineRadio_Field_Transmission_FR.wav",
    mime_type: "audio/wav",
    size_bytes: 960000,
    sanctuary_id: "OC02",
    station_code: "OC02",
    latitude: 47.9,
    longitude: -124.8,
    geo_qa_flag: null,
  },
];

export default function VaultPage() {
  const [assets, setAssets] = useState<AssetOut[]>(MOCK_ASSETS);
  const [filterSanctuary, setFilterSanctuary] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isWizardOpen, setIsWizardOpen] = useState(false);

  // Ingest Wizard State
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sanctuaryCode, setSanctuaryCode] = useState("CI01");
  const [depthMeters, setDepthMeters] = useState(182);
  const [computedSha256, setComputedSha256] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    listAssets()
      .then((items) => {
        if (items && items.length > 0) setAssets(items);
      })
      .catch(() => {});
  }, []);

  const filteredAssets = assets.filter((asset) => {
    const matchesSanc =
      filterSanctuary === "ALL" || (asset.sanctuary_id ?? "").includes(filterSanctuary);
    const matchesQuery =
      searchQuery === "" ||
      (asset.original_filename ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      asset.sha256.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSanc && matchesQuery;
  });

  async function handleFileSelect(file: File) {
    setSelectedFile(file);
    // Simulated fast Blake3/SHA256 client pre-calculation
    const buffer = await file.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    const hashArray = Array.from(new Uint8Array(digest));
    const hashHex = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
    setComputedSha256(hashHex);
    setWizardStep(2);
  }

  async function handleCompleteIngest() {
    if (!selectedFile) return;
    setIsUploading(true);
    setWizardStep(3);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("sanctuary_id", sanctuaryCode);
    formData.append("station_code", sanctuaryCode);

    try {
      await ingestAudioFile(formData);
      const updated = await listAssets();
      setAssets(updated);
    } catch {
      // Add local preview asset if API is mock-running
      setAssets((prev) => [
        {
          sha256: computedSha256 || "9f82c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b899",
          asset_type: "audio",
          original_filename: selectedFile.name,
          mime_type: selectedFile.type || "audio/wav",
          size_bytes: selectedFile.size,
          sanctuary_id: sanctuaryCode,
          station_code: sanctuaryCode,
          latitude: null,
          longitude: null,
          geo_qa_flag: null,
        },
        ...prev,
      ]);
    } finally {
      setIsUploading(false);
      setTimeout(() => {
        setIsWizardOpen(false);
        setWizardStep(1);
        setSelectedFile(null);
      }, 1000);
    }
  }

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-8"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Sovereign Acoustic Vault
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Immutably sealed raw hydrophone recordings, NOAA sanctuary telemetry XML, and diarized audio assets.
            </p>
          </div>
          <button
            onClick={() => {
              setIsWizardOpen(true);
              setWizardStep(1);
            }}
            className="flex items-center gap-2 rounded-lg bg-tide-500 px-4 py-2 text-xs font-bold text-abyss-950 transition hover:bg-tide-400"
          >
            <Plus size={16} /> Ingest Acoustic Asset
          </button>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-white/10 bg-abyss-900/70 p-4">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <Search size={16} className="text-slate-400" />
            <input
              type="text"
              placeholder="Search by filename or SHA-256 hash..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent text-xs text-white placeholder-slate-500 outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter size={14} className="text-slate-400" />
            <span className="text-xs text-slate-400">Sanctuary:</span>
            {["ALL", "CI", "SB", "OC", "FK"].map((code) => (
              <button
                key={code}
                onClick={() => setFilterSanctuary(code)}
                className={`rounded px-2.5 py-1 text-xs font-mono font-medium transition ${
                  filterSanctuary === code
                    ? "bg-tide-500/20 text-tide-300 border border-tide-400/40"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                {code}
              </button>
            ))}
          </div>
        </div>

        {/* Asset Table / Cards */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/70 overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/10 bg-abyss-950/60 font-mono text-[11px] uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-5 py-3.5">Asset &amp; Cryptographic Hash</th>
                <th className="px-5 py-3.5">Sanctuary Station</th>
                <th className="px-5 py-3.5">Format</th>
                <th className="px-5 py-3.5">Size</th>
                <th className="px-5 py-3.5">Geo QA</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredAssets.map((asset) => {
                const isAudio = asset.mime_type.startsWith("audio");
                return (
                  <tr key={asset.sha256} className="transition hover:bg-white/5">
                    <td className="px-5 py-4">
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-abyss-950 text-tide-300 border border-white/10">
                          {isAudio ? <FileAudio size={16} /> : <FileText size={16} />}
                        </span>
                        <div>
                          <p className="font-semibold text-white">
                            {asset.original_filename ?? "untitled"}
                          </p>
                          <p className="mt-1 font-mono text-[11px] text-slate-500 truncate max-w-xs">
                            {asset.sha256}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="rounded bg-tide-500/10 px-2 py-0.5 font-mono text-xs text-tide-300 border border-tide-400/20">
                        {asset.sanctuary_id ?? "—"}
                      </span>
                      {asset.station_code && (
                        <span className="ml-2 text-slate-400 text-[11px]">{asset.station_code}</span>
                      )}
                    </td>
                    <td className="px-5 py-4 font-mono text-slate-300">{asset.mime_type}</td>
                    <td className="px-5 py-4 font-mono text-slate-300">
                      {(asset.size_bytes / 1_000_000).toFixed(2)} MB
                    </td>
                    <td className="px-5 py-4">
                      <span className="rounded px-2 py-0.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
                        {asset.geo_qa_flag ?? "OK"}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      {isAudio ? (
                        <Link
                          to={`/workbench?sha256=${asset.sha256}`}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-3 py-1.5 text-xs font-semibold text-tide-300 border border-tide-400/30 transition hover:bg-tide-500/30"
                        >
                          <Waves size={13} /> Open Workbench
                        </Link>
                      ) : (
                        <Link
                          to={`/documents?sha256=${asset.sha256}`}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-300 border border-white/10 transition hover:bg-white/10 hover:text-white"
                        >
                          <FileText size={13} /> View Chunks
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Multi-Step Ingest Wizard Modal */}
        {isWizardOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/80 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-full max-w-lg rounded-2xl border border-white/10 bg-abyss-900 p-6 shadow-2xl space-y-6"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div className="flex items-center gap-2">
                  <Upload size={18} className="text-tide-400" />
                  <h2 className="text-base font-bold text-white font-display">
                    Sovereign Ingest Wizard
                  </h2>
                </div>
                <button
                  onClick={() => setIsWizardOpen(false)}
                  className="rounded p-1 text-slate-400 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Step indicator */}
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className={wizardStep === 1 ? "text-tide-400 font-bold" : ""}>
                  1. Audio &amp; Metadata
                </span>
                <span>→</span>
                <span className={wizardStep === 2 ? "text-tide-400 font-bold" : ""}>
                  2. Cryptographic Seal
                </span>
                <span>→</span>
                <span className={wizardStep === 3 ? "text-tide-400 font-bold" : ""}>
                  3. 7-Stage DAG
                </span>
              </div>

              {/* Step 1: Dropzone & Metadata */}
              {wizardStep === 1 && (
                <div className="space-y-4">
                  <div className="rounded-xl border-2 border-dashed border-white/10 p-6 text-center transition hover:border-tide-400/50">
                    <Upload size={28} className="mx-auto text-slate-500" />
                    <p className="mt-2 text-xs font-medium text-slate-300">
                      Drag &amp; drop marine hydrophone audio (.wav, .flac) or XML telemetry
                    </p>
                    <input
                      type="file"
                      id="fileInput"
                      className="hidden"
                      accept=".wav,.flac,.xml,.pdf"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleFileSelect(file);
                      }}
                    />
                    <label
                      htmlFor="fileInput"
                      className="mt-3 inline-block cursor-pointer rounded-lg bg-white/10 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-white/20"
                    >
                      Browse Files
                    </label>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1">
                        SANCTUARY CODE
                      </label>
                      <select
                        value={sanctuaryCode}
                        onChange={(e) => setSanctuaryCode(e.target.value)}
                        className="w-full rounded bg-abyss-950 border border-white/10 px-3 py-2 text-white outline-none"
                      >
                        <option value="CI01">CI01 - Channel Islands</option>
                        <option value="SB01">SB01 - Stellwagen Bank</option>
                        <option value="OC02">OC02 - Olympic Coast</option>
                        <option value="FK01">FK01 - Florida Keys</option>
                        <option value="MB01">MB01 - Monterey Bay</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1">
                        DEPLOYMENT DEPTH (M)
                      </label>
                      <input
                        type="number"
                        value={depthMeters}
                        onChange={(e) => setDepthMeters(Number(e.target.value))}
                        className="w-full rounded bg-abyss-950 border border-white/10 px-3 py-2 text-white outline-none font-mono"
                      >
                      </input>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Blake3 / SHA-256 Hash Verification */}
              {wizardStep === 2 && (
                <div className="space-y-4 text-xs">
                  <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4 text-emerald-300">
                    <p className="font-semibold flex items-center gap-1.5">
                      <ShieldCheck size={16} /> Pre-Ingest Integrity Digest Computed
                    </p>
                    <p className="mt-2 font-mono text-[11px] break-all text-slate-300">
                      SHA-256: {computedSha256}
                    </p>
                  </div>

                  <div className="rounded-lg bg-abyss-950 p-3 space-y-2 text-slate-300 border border-white/5">
                    <div className="flex justify-between">
                      <span className="text-slate-500">File Name:</span>
                      <span className="font-semibold">{selectedFile?.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Size:</span>
                      <span className="font-mono">
                        {selectedFile ? (selectedFile.size / 1024 / 1024).toFixed(2) : 0} MB
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Target Station:</span>
                      <span className="font-mono text-tide-300">{sanctuaryCode}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2">
                    <button
                      onClick={() => setWizardStep(1)}
                      className="rounded-lg px-3 py-1.5 text-slate-400 hover:text-white"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleCompleteIngest}
                      disabled={isUploading}
                      className="flex items-center gap-1.5 rounded-lg bg-tide-500 px-4 py-2 font-bold text-abyss-950 transition hover:bg-tide-400 disabled:opacity-50"
                    >
                      {isUploading ? "Sealing..." : "Trigger 7-Stage Pipeline"} <ArrowRight size={14} />
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Pipeline Trigger Progress */}
              {wizardStep === 3 && (
                <div className="py-6 text-center space-y-4">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-tide-500/20 text-tide-300 border border-tide-400/30">
                    <Waves size={28} className="animate-pulse" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Sealing Asset &amp; Scheduling Pipeline</h3>
                    <p className="mt-1 text-xs text-slate-400">
                      Dispatched to Whisper v3 Turbo, pyannote diarization, and AST classifiers on Blackwell GPU...
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          </div>
        )}
      </motion.div>
    </AppShell>
  );
}
