import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  AudioWaveform,
  Cpu,
  Layers,
  Search,
  Sparkles,
  Table,
} from "lucide-react";
import { Link } from "react-router-dom";

import AppShell from "@/components/ui/AppShell";
import {
  searchAcousticText,
  searchDebug,
  searchHybrid,
  type ScoreDebugItem,
  type SearchResult,
} from "@/lib/api";

type SearchMode = "hybrid" | "acoustic" | "debugger";

const MOCK_HYBRID_RESULTS: SearchResult[] = [
  {
    asset_sha256: "b6d8f8a12c4e6f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a",
    score: 0.032,
    rerank_score: 0.942,
    payload: {
      text: "Channel Islands station CI01 recording initiation. Low frequency tonal vocalization detected on channel one. Estimated 20Hz pulse train.",
      sanctuary_code: "CI01",
      start_sec: 12.5,
      end_sec: 24.0,
      speaker_label: "ACOUSTIC_ANALYST",
    },
  },
  {
    asset_sha256: "c7e9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9",
    score: 0.028,
    rerank_score: 0.887,
    payload: {
      text: "Fin Whale pulse train detected in Stellwagen Bank during autumn migratory passage.",
      sanctuary_code: "SB01",
      start_sec: 4.0,
      end_sec: 18.0,
      speaker_label: "HYDROPHONE",
    },
  },
];

const MOCK_DEBUG_ITEMS: ScoreDebugItem[] = [
  {
    id: "seg-101",
    text: "Low frequency tonal vocalization detected on channel one. Estimated 20Hz pulse train.",
    asset_sha256: "b6d8f8a12c4e6f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a",
    dense_score: 0.842,
    sparse_score: 14.28,
    dense_rank: 2,
    sparse_rank: 5,
    rrf_score: 0.0315,
    rrf_rank: 3,
    rerank_score: 0.942,
    final_rank: 1,
    rank_shift: 2,
  },
  {
    id: "seg-102",
    text: "Fin Whale pulse train detected in Stellwagen Bank during autumn migratory passage.",
    asset_sha256: "c7e9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9",
    dense_score: 0.865,
    sparse_score: 11.45,
    dense_rank: 1,
    sparse_rank: 8,
    rrf_score: 0.0308,
    rrf_rank: 2,
    rerank_score: 0.887,
    final_rank: 2,
    rank_shift: 0,
  },
  {
    id: "seg-103",
    text: "Transient cavitation signature approaching from northwest traffic lane, speed 14 knots.",
    asset_sha256: "e9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
    dense_score: 0.791,
    sparse_score: 18.91,
    dense_rank: 4,
    sparse_rank: 1,
    rrf_score: 0.0322,
    rrf_rank: 1,
    rerank_score: 0.741,
    final_rank: 3,
    rank_shift: -2,
  },
];

export default function SearchStudioPage() {
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [query, setQuery] = useState("Fin whale vocalization and vessel cavitation");
  const [collection, setCollection] = useState<"transcript_segments" | "document_chunks">(
    "transcript_segments"
  );
  const [isSearching, setIsSearching] = useState(false);

  const [results, setResults] = useState<SearchResult[]>(MOCK_HYBRID_RESULTS);
  const [debugItems, setDebugItems] = useState<ScoreDebugItem[]>(MOCK_DEBUG_ITEMS);

  async function handleSearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    try {
      if (mode === "hybrid") {
        const res = await searchHybrid(query, collection, 20, true);
        if (res.results) setResults(res.results);
      } else if (mode === "acoustic") {
        const res = await searchAcousticText(query, 20);
        if (res.results) setResults(res.results);
      } else if (mode === "debugger") {
        const res = await searchDebug(query, collection, 15);
        if (res.results) setDebugItems(res.results);
      }
    } catch {
      // Keep mock results if standalone
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-6"
      >
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display">
            Multimodal Search Studio
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Sovereign dense+sparse reciprocal rank fusion (RRF) with BGE-M3 and cross-encoder re-ranking on NVIDIA DGX Spark GB10.
          </p>
        </div>

        {/* Search Mode Tab Selectors */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-abyss-900/80 p-1">
            <button
              onClick={() => {
                setMode("hybrid");
                handleSearch();
              }}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                mode === "hybrid"
                  ? "bg-tide-500/20 text-tide-300 border border-tide-400/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Layers size={14} /> Hybrid Text &amp; Transcripts
            </button>
            <button
              onClick={() => {
                setMode("acoustic");
                handleSearch();
              }}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                mode === "acoustic"
                  ? "bg-tide-500/20 text-tide-300 border border-tide-400/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <AudioWaveform size={14} /> Acoustic Soundscape (CLAP)
            </button>
            <button
              onClick={() => {
                setMode("debugger");
                handleSearch();
              }}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                mode === "debugger"
                  ? "bg-signal-amber/20 text-signal-amber border border-signal-amber/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Table size={14} /> Retrieval Score Debugger
            </button>
          </div>

          {mode !== "acoustic" && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 font-mono">Collection:</span>
              <select
                value={collection}
                onChange={(e) => setCollection(e.target.value as any)}
                className="rounded bg-abyss-900 border border-white/10 px-2.5 py-1 text-white text-xs outline-none"
              >
                <option value="transcript_segments">transcript_segments</option>
                <option value="document_chunks">document_chunks</option>
              </select>
            </div>
          )}
        </div>

        {/* Master Query Search Bar */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search
              size={18}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                mode === "acoustic"
                  ? "Describe acoustic soundscape (e.g. 'high frequency dolphin whistles in shallow reef')..."
                  : "Search transcripts, species vocalizations, and telemetry docs..."
              }
              className="w-full rounded-xl border border-white/10 bg-abyss-900/90 py-3.5 pl-11 pr-4 text-sm text-white placeholder-slate-500 outline-none focus:border-tide-400/50"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching}
            className="flex items-center gap-2 rounded-xl bg-tide-500 px-6 py-3.5 text-sm font-bold text-abyss-950 transition hover:bg-tide-400 disabled:opacity-50"
          >
            <Sparkles size={16} /> {isSearching ? "Searching..." : "Search"}
          </button>
        </form>

        {/* Results View: Standard Hybrid / Acoustic */}
        {mode !== "debugger" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>{results.length} EVIDENCE CANDIDATES RETRIEVED</span>
              <span>BGE-M3 + BAAI/bge-reranker-v2-m3 Cross-Encoder</span>
            </div>

            <div className="space-y-3">
              {results.map((res, idx) => {
                const payload = res.payload || {};
                return (
                  <div
                    key={res.asset_sha256 + idx}
                    className="rounded-xl border border-white/10 bg-abyss-900/70 p-5 transition hover:border-white/20 space-y-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-tide-500/20 text-xs font-mono font-bold text-tide-300">
                          #{idx + 1}
                        </span>
                        <span className="font-mono text-xs text-slate-400">
                          Sanctuary {payload.sanctuary_code || "CI01"}
                        </span>
                        {payload.start_sec !== undefined && (
                          <span className="font-mono text-xs text-tide-400">
                            @{payload.start_sec}s
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 text-xs font-mono">
                        {res.rerank_score !== null && (
                          <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-emerald-400 border border-emerald-500/20">
                            Cross-Encoder: {(res.rerank_score * 100).toFixed(1)}%
                          </span>
                        )}
                        <span className="rounded bg-white/5 px-2 py-0.5 text-slate-400">
                          RRF: {res.score.toFixed(4)}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-200 leading-relaxed font-sans">{payload.text}</p>

                    <div className="flex items-center justify-between border-t border-white/5 pt-3">
                      <span className="font-mono text-[11px] text-slate-500 truncate max-w-md">
                        SHA-256: {res.asset_sha256}
                      </span>
                      <Link
                        to={`/workbench?sha256=${res.asset_sha256}`}
                        className="flex items-center gap-1 text-xs font-semibold text-tide-400 hover:underline"
                      >
                        Inspect in Workbench <ArrowRight size={12} />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Retrieval Score Debugger Table */}
        {mode === "debugger" && (
          <div className="space-y-4">
            <div className="rounded-xl border border-signal-amber/30 bg-signal-amber/5 p-4 text-xs text-signal-amber space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <Cpu size={16} /> Retrieval Fusion &amp; Re-ranking Diagnostics
              </p>
              <p className="text-slate-300">
                Shows dense semantic dot-product scores alongside sparse BM25 lexical match scores, weighted reciprocal rank fusion (RRF), and cross-encoder score shifts.
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-abyss-900/80 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 bg-abyss-950/80 font-mono text-[11px] uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Final Rank</th>
                    <th className="px-4 py-3">Evidence Snippet</th>
                    <th className="px-4 py-3">Dense (BGE-M3)</th>
                    <th className="px-4 py-3">Sparse (Lexical)</th>
                    <th className="px-4 py-3">RRF Score</th>
                    <th className="px-4 py-3">Re-Ranker</th>
                    <th className="px-4 py-3 text-right">Rank Shift</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {debugItems.map((item) => {
                    const shiftPositive = item.rank_shift > 0;
                    const shiftNegative = item.rank_shift < 0;

                    return (
                      <tr key={item.id} className="transition hover:bg-white/5">
                        <td className="px-4 py-3 font-mono font-bold text-white">
                          #{item.final_rank}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-200 line-clamp-2 max-w-sm">
                            {item.text}
                          </p>
                          <span className="font-mono text-[10px] text-slate-500">
                            {item.asset_sha256.slice(0, 16)}...
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-300">
                          {item.dense_score.toFixed(3)}{" "}
                          <span className="text-[10px] text-slate-500">(#{item.dense_rank})</span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-300">
                          {item.sparse_score.toFixed(2)}{" "}
                          <span className="text-[10px] text-slate-500">(#{item.sparse_rank})</span>
                        </td>
                        <td className="px-4 py-3 font-mono text-tide-300">
                          {item.rrf_score.toFixed(4)}{" "}
                          <span className="text-[10px] text-slate-500">(#{item.rrf_rank})</span>
                        </td>
                        <td className="px-4 py-3 font-mono font-bold text-emerald-400">
                          {(item.rerank_score * 100).toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-bold">
                          {shiftPositive && (
                            <span className="text-emerald-400 flex items-center justify-end gap-0.5">
                              <ArrowUp size={12} /> +{item.rank_shift}
                            </span>
                          )}
                          {shiftNegative && (
                            <span className="text-signal-coral flex items-center justify-end gap-0.5">
                              <ArrowDown size={12} /> {item.rank_shift}
                            </span>
                          )}
                          {item.rank_shift === 0 && (
                            <span className="text-slate-500">0</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </motion.div>
    </AppShell>
  );
}
