import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Upload,
  LayoutGrid,
  Clock,
  Map as MapIcon,
  Search,
  Sparkles,
  BarChart3,
  Settings as SettingsIcon,
  CommandIcon,
} from "lucide-react";
import "./CommandPalette.css";

interface Entry {
  label: string;
  hint?: string;
  icon: typeof Upload;
  action: (navigate: ReturnType<typeof useNavigate>) => void;
}

const ENTRIES: Entry[] = [
  { label: "Upload", hint: "Go to Upload", icon: Upload, action: (nav) => nav("/upload") },
  { label: "Library", hint: "Go to Library", icon: LayoutGrid, action: (nav) => nav("/library") },
  { label: "Timeline", hint: "Go to Timeline", icon: Clock, action: (nav) => nav("/timeline") },
  { label: "Map", hint: "Go to Map", icon: MapIcon, action: (nav) => nav("/map") },
  { label: "Search", hint: "Go to Search", icon: Search, action: (nav) => nav("/search") },
  { label: "Ask AI", hint: "Go to Ask AI", icon: Sparkles, action: (nav) => nav("/ask") },
  { label: "Dashboard", hint: "Go to Dashboard", icon: BarChart3, action: (nav) => nav("/dashboard") },
  { label: "Settings", hint: "Go to Settings", icon: SettingsIcon, action: (nav) => nav("/settings") },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ENTRIES;
    return ENTRIES.filter((e) => e.label.toLowerCase().includes(q));
  }, [query]);

  const run = (entry: Entry) => {
    entry.action(navigate);
    setOpen(false);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (filtered.length > 0) {
      run(filtered[0]);
    } else if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
      setOpen(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="cmdk-overlay" />
        <Dialog.Content className="cmdk-content glass-card" aria-describedby={undefined}>
          <Dialog.Title className="cmdk-title">
            <CommandIcon size={14} /> Command palette
          </Dialog.Title>
          <form onSubmit={onSubmit}>
            <input
              autoFocus
              className="cmdk-input"
              placeholder="Jump to a page, or type to search…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>
          <div className="cmdk-list">
            {filtered.length === 0 ? (
              <div className="cmdk-empty">Press Enter to search "{query}"</div>
            ) : (
              filtered.map((entry) => (
                <button key={entry.label} type="button" className="cmdk-item" onClick={() => run(entry)}>
                  <entry.icon size={16} />
                  <span>{entry.label}</span>
                  {entry.hint && <span className="cmdk-hint">{entry.hint}</span>}
                </button>
              ))
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
