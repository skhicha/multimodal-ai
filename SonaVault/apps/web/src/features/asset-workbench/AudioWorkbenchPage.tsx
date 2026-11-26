import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ChevronRight,
  Edit3,
  Globe,
  Headphones,
  Languages,
  Pause,
  Play,
  Save,
  Waves,
  X,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";

import AppShell from "@/components/ui/AppShell";
import {
  getAcousticEvents,
  getTranscript,
  translateTranscript,
  updateTranscriptSegment,
  type AcousticEventOut,
  type TranscriptSegmentOut,
} from "@/lib/api";

const DEFAULT_SHA256 = "b6d8f8a12c4e6f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a";

const MOCK_SEGMENTS: TranscriptSegmentOut[] = [
  {
    id: "seg-1",
    seg_index: 0,
    start_sec: 0.0,
    end_sec: 8.4,
    text_redacted: "Channel Islands station CI01 recording initiation. Hydrophone depth 182 meters.",
    speaker_label: "OPERATOR",
    source_lang: "en",
    translations_json: {
      fr: "Initialisation de l'enregistrement de la station CI01 des îles Channel. Profondeur de l'hydrophone 182 mètres.",
      es: "Iniciación de la grabación de la estación CI01 de Channel Islands. Profundidad del hidrófono 182 metros.",
      ja: "チャンネル諸島ステーションCI01録音開始。ハイドロフォン深度182メートル。",
    },
    entities_json: null,
    is_hitl_override: false,
    created_at: "2024-10-14T12:05:00Z",
  },
  {
    id: "seg-2",
    seg_index: 1,
    start_sec: 12.5,
    end_sec: 24.0,
    text_redacted: "Low frequency tonal vocalization detected on channel one. Estimated 20Hz pulse train.",
    speaker_label: "ACOUSTIC_ANALYST",
    source_lang: "en",
    translations_json: {
      fr: "Vocalisation tonale à basse fréquence détectée sur le canal un. Train d'impulsions estimé à 20 Hz.",
      es: "Vocalización tonal de baja frecuencia detectada en el canal uno. Tren de pulsos estimado de 20 Hz.",
      ja: "チャンネル1で低周波トーン発声を検出。推定20Hzのパルストレイン。",
    },
    entities_json: null,
    is_hitl_override: false,
    created_at: "2024-10-14T12:05:12Z",
  },
  {
    id: "seg-3",
    seg_index: 2,
    start_sec: 28.2,
    end_sec: 42.6,
    text_redacted: "Transient cavitation signature approaching from northwest traffic lane, speed 14 knots.",
    speaker_label: "VESSEL_WATCH",
    source_lang: "en",
    translations_json: {
      fr: "Signature de cavitation transitoire approchant de la voie de circulation nord-ouest, vitesse 14 nœuds.",
      es: "Firma de cavitación transitoria que se aproxima desde el carril de tráfico del noroeste, velocidad 14 nudos.",
      ja: "北西航路から過渡的キャビテーションシグネチャが接近、速度14ノット。",
    },
    entities_json: null,
    is_hitl_override: false,
    created_at: "2024-10-14T12:05:28Z",
  },
];

const MOCK_EVENTS: AcousticEventOut[] = [
  {
    id: "ev-1",
    window_start_sec: 4.0,
    window_end_sec: 18.0,
    audioset_label: "Fin Whale (Balaenoptera physalus) 20Hz",
    confidence: 0.94,
    spl_db_broadband: null,
    is_hitl_override: false,
    created_at: "2024-10-14T12:05:00Z",
  },
  {
    id: "ev-2",
    window_start_sec: 22.0,
    window_end_sec: 38.0,
    audioset_label: "Commercial Cargo Vessel Cavitation",
    confidence: 0.91,
    spl_db_broadband: null,
    is_hitl_override: false,
    created_at: "2024-10-14T12:05:22Z",
  },
  {
    id: "ev-3",
    window_start_sec: 45.0,
    window_end_sec: 58.0,
    audioset_label: "Snapping Shrimp Ambient Cluster",
    confidence: 0.78,
    spl_db_broadband: null,
    is_hitl_override: false,
    created_at: "2024-10-14T12:05:45Z",
  },
];

export default function AudioWorkbenchPage() {
  const [searchParams] = useSearchParams();
  const sha256Param = searchParams.get("sha256") || DEFAULT_SHA256;

  const [currentTime, setCurrentTime] = useState(0);
  const [duration] = useState(60.0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeLang, setActiveLang] = useState<string>("original");
  const [isTranslating, setIsTranslating] = useState(false);

  const [segments, setSegments] = useState<TranscriptSegmentOut[]>(MOCK_SEGMENTS);
  const [events, setEvents] = useState<AcousticEventOut[]>(MOCK_EVENTS);

  // HITL Segment Edit Drawer
  const [editingSegment, setEditingSegment] = useState<TranscriptSegmentOut | null>(null);
  const [editText, setEditText] = useState("");
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const playIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    getTranscript(sha256Param)
      .then((res) => {
        if (res.segments && res.segments.length > 0) setSegments(res.segments);
      })
      .catch(() => {});

    getAcousticEvents(sha256Param)
      .then((res) => {
        if (res.events && res.events.length > 0) setEvents(res.events);
      })
      .catch(() => {});
  }, [sha256Param]);

  // Audio Playback Timer
  useEffect(() => {
    if (isPlaying) {
      playIntervalRef.current = window.setInterval(() => {
        setCurrentTime((prev) => {
          if (prev >= duration) {
            setIsPlaying(false);
            return 0;
          }
          return prev + 0.2;
        });
      }, 200);
    } else {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    }
    return () => {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    };
  }, [isPlaying, duration]);

  async function handleLanguageSwitch(lang: string) {
    setActiveLang(lang);
    if (lang === "original") return;

    // Check if translation exists, otherwise call API
    const needsTranslation = segments.some((s) => !s.translations_json || !s.translations_json[lang]);
    if (needsTranslation) {
      setIsTranslating(true);
      try {
        const res = await translateTranscript(sha256Param, lang);
        if (res.segments) setSegments(res.segments);
      } catch {
        // Mock fallback if offline
      } finally {
        setIsTranslating(false);
      }
    }
  }

  function handleSeek(targetSec: number) {
    setCurrentTime(Math.min(duration, Math.max(0, targetSec)));
  }

  async function handleSaveSegmentEdit() {
    if (!editingSegment) return;
    setIsSavingEdit(true);
    try {
      await updateTranscriptSegment(sha256Param, editingSegment.id, editText);
      setSegments((prev) =>
        prev.map((s) => (s.id === editingSegment.id ? { ...s, text_redacted: editText } : s))
      );
    } catch {
      setSegments((prev) =>
        prev.map((s) => (s.id === editingSegment.id ? { ...s, text_redacted: editText } : s))
      );
    } finally {
      setIsSavingEdit(false);
      setEditingSegment(null);
    }
  }

  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 10);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${ms}`;
  };

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-6"
      >
        {/* Header */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-tide-500/20 text-tide-300 border border-tide-400/30">
                <Headphones size={16} />
              </span>
              <h1 className="text-xl font-bold tracking-tight text-white font-display">
                Multimodal Acoustic Workbench
              </h1>
            </div>
            <p className="mt-1 font-mono text-xs text-slate-400 truncate max-w-2xl">
              TARGET SHA-256: {sha256Param}
            </p>
          </div>

          {/* MADLAD-400 Translation Language Switcher */}
          <div className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-abyss-900/80 p-1">
            <span className="flex items-center gap-1 px-2 text-xs font-medium text-slate-400">
              <Languages size={14} className="text-tide-400" /> MT:
            </span>
            {[
              { id: "original", label: "Original" },
              { id: "fr", label: "FR" },
              { id: "es", label: "ES" },
              { id: "ja", label: "JA" },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => handleLanguageSwitch(id)}
                className={`rounded px-2.5 py-1 text-xs font-mono font-medium transition ${
                  activeLang === id
                    ? "bg-tide-500/20 text-tide-300 border border-tide-400/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Synchronized Master Audio Waveform Scrubber Player */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/90 p-6 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-tide-500 text-abyss-950 font-bold transition hover:bg-tide-400 shadow-lg shadow-tide-500/20"
              >
                {isPlaying ? <Pause size={20} /> : <Play size={20} className="ml-0.5" />}
              </button>
              <div>
                <p className="text-sm font-bold font-mono text-white">
                  {formatTime(currentTime)} <span className="text-slate-500">/ {formatTime(duration)}</span>
                </p>
                <p className="text-[11px] text-slate-400 font-mono">
                  Opus / PCM 48kHz • Whisper v3 Turbo Diarized
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="rounded px-2 py-0.5 text-[11px] font-mono text-tide-300 bg-tide-500/10 border border-tide-400/20">
                Playhead: {(currentTime / duration * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Interactive Waveform Canvas Bar Scrubber */}
          <div
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const clickFraction = (e.clientX - rect.left) / rect.width;
              handleSeek(clickFraction * duration);
            }}
            className="group relative h-24 w-full cursor-pointer rounded-lg bg-abyss-950 p-2 border border-white/10 overflow-hidden flex items-end gap-1"
          >
            {/* Waveform bars */}
            {Array.from({ length: 90 }).map((_, i) => {
              const barFraction = i / 90;
              const isPast = currentTime / duration >= barFraction;
              // deterministic visual audio wave pattern
              const heightPct = Math.max(
                15,
                Math.sin(i * 0.25) * 40 + Math.cos(i * 0.7) * 35 + 20
              );

              return (
                <div
                  key={i}
                  style={{ height: `${heightPct}%` }}
                  className={`w-full rounded-xs transition ${
                    isPast
                      ? "bg-tide-400 shadow-[0_0_8px_rgba(45,212,191,0.5)]"
                      : "bg-abyss-800 group-hover:bg-abyss-700"
                  }`}
                />
              );
            })}

            {/* Playhead vertical marker */}
            <div
              style={{ left: `${(currentTime / duration) * 100}%` }}
              className="absolute top-0 bottom-0 w-0.5 bg-signal-coral shadow-[0_0_10px_#fb7185] pointer-events-none"
            >
              <div className="h-2 w-2 -ml-[3px] rounded-full bg-signal-coral" />
            </div>
          </div>
        </div>

        {/* Diarization Turns & AST Events Split Grid */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Whisper Transcript & Diarization Turns Column */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-xl border border-white/10 bg-abyss-900/80 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Waves size={16} className="text-tide-400" />
                  <h2 className="text-sm font-semibold text-white">
                    Whisper v3 Turbo Transcript &amp; Pyannote Diarization
                  </h2>
                </div>
                {isTranslating && (
                  <span className="text-xs font-mono text-tide-300 animate-pulse flex items-center gap-1">
                    <Globe size={12} /> Translating with MADLAD-400...
                  </span>
                )}
              </div>

              {/* Segments List */}
              <div className="space-y-3">
                {segments.map((seg) => {
                  const isActive = currentTime >= seg.start_sec && currentTime <= seg.end_sec;
                  const displayedText =
                    activeLang !== "original" && seg.translations_json?.[activeLang]
                      ? seg.translations_json[activeLang]
                      : seg.text_redacted;

                  return (
                    <div
                      key={seg.id}
                      className={`group rounded-lg p-3.5 border transition ${
                        isActive
                          ? "bg-tide-500/15 border-tide-400/50 shadow-md shadow-tide-500/5"
                          : "bg-abyss-950/40 border-white/5 hover:border-white/15"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleSeek(seg.start_sec)}
                            className="font-mono text-[11px] font-bold text-tide-400 hover:underline flex items-center gap-1"
                          >
                            <Play size={10} /> {formatTime(seg.start_sec)} - {formatTime(seg.end_sec)}
                          </button>
                          <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] font-mono text-slate-400">
                            {seg.speaker_label || "SPEAKER_00"}
                          </span>
                        </div>
                        <button
                          onClick={() => {
                            setEditingSegment(seg);
                            setEditText(seg.text_redacted || "");
                          }}
                          className="opacity-0 group-hover:opacity-100 transition rounded p-1 text-slate-400 hover:text-white hover:bg-white/10"
                          title="HITL Analyst Correction"
                        >
                          <Edit3 size={13} />
                        </button>
                      </div>

                      <p className="text-xs text-slate-200 leading-relaxed font-sans">{displayedText}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* AST Acoustic Event Classifications Column */}
          <div className="space-y-4">
            <div className="rounded-xl border border-white/10 bg-abyss-900/80 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Activity size={16} className="text-tide-400" />
                  <h3 className="text-sm font-semibold text-white">AST Acoustic Classifications</h3>
                </div>
                <span className="font-mono text-[10px] text-slate-500">AudioSet 527</span>
              </div>

              <div className="space-y-3">
                {events.map((ev) => {
                  const isActive =
                    currentTime >= ev.window_start_sec && currentTime <= ev.window_end_sec;

                  return (
                    <button
                      key={ev.id}
                      onClick={() => handleSeek(ev.window_start_sec)}
                      className={`w-full text-left rounded-lg p-3 border transition ${
                        isActive
                          ? "bg-signal-amber/15 border-signal-amber/40"
                          : "bg-abyss-950/40 border-white/5 hover:border-white/15"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-white truncate max-w-[170px]">
                          {ev.audioset_label}
                        </span>
                        <span className="font-mono font-bold text-signal-amber">
                          {(ev.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>
                          {formatTime(ev.window_start_sec)} - {formatTime(ev.window_end_sec)}
                        </span>
                        <span className="text-tide-400 flex items-center gap-0.5">
                          Seek <ChevronRight size={10} />
                        </span>
                      </div>
                      {/* Confidence bar */}
                      <div className="mt-2 h-1 w-full rounded-full bg-abyss-800 overflow-hidden">
                        <div
                          style={{ width: `${ev.confidence * 100}%` }}
                          className="h-full bg-signal-amber rounded-full"
                        />
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* HITL Edit Drawer Modal */}
        {editingSegment && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/80 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-full max-w-lg rounded-2xl border border-white/10 bg-abyss-900 p-6 shadow-2xl space-y-4"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Edit3 size={16} className="text-tide-400" />
                  <h3 className="text-sm font-bold text-white font-display">
                    Human-in-the-Loop Transcript Correction
                  </h3>
                </div>
                <button
                  onClick={() => setEditingSegment(null)}
                  className="rounded p-1 text-slate-400 hover:text-white"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between font-mono text-slate-400">
                  <span>Segment: {editingSegment.id}</span>
                  <span>
                    Time: {formatTime(editingSegment.start_sec)} - {formatTime(editingSegment.end_sec)}
                  </span>
                </div>
                <textarea
                  rows={4}
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="w-full rounded-lg bg-abyss-950 border border-white/10 p-3 text-xs text-white outline-none focus:border-tide-400/50"
                  placeholder="Enter corrected transcript text..."
                />
                <p className="text-[11px] text-slate-500">
                  Saving this correction updates the sovereign database and triggers an incremental BGE-M3 dense+sparse re-indexing of this chunk in Qdrant.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setEditingSegment(null)}
                  className="rounded px-3 py-1.5 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveSegmentEdit}
                  disabled={isSavingEdit}
                  className="flex items-center gap-1.5 rounded-lg bg-tide-500 px-4 py-2 text-xs font-bold text-abyss-950 transition hover:bg-tide-400 disabled:opacity-50"
                >
                  <Save size={14} /> {isSavingEdit ? "Saving..." : "Save & Re-Index"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </motion.div>
    </AppShell>
  );
}
