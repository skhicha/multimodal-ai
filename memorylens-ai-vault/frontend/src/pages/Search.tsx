import type React from "react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { SearchIcon, Video, ImageIcon } from "lucide-react";
import { api, withAuth, type SearchResult } from "../lib/api";
import { Skeleton } from "../components/Skeleton";
import "./Search.css";

// The backend highlights matches with literal `<mark>...</mark>` around
// raw (unescaped) snippet text from SQLite FTS5's snippet(). Since that text
// can come from a user-controlled filename, rendering it as HTML would be a
// stored-XSS hole. Parse out just the two known delimiters ourselves and let
// React escape every other character as plain text.
function renderSnippet(snippet: string) {
  const parts = snippet.split(/(<mark>|<\/mark>)/);
  let highlighting = false;
  const nodes: React.ReactNode[] = [];
  parts.forEach((part, i) => {
    if (part === "<mark>") {
      highlighting = true;
      return;
    }
    if (part === "</mark>") {
      highlighting = false;
      return;
    }
    if (!part) return;
    nodes.push(highlighting ? <mark key={i}>{part}</mark> : <span key={i}>{part}</span>);
  });
  return nodes;
}

export function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const runSearch = async (query: string) => {
    if (!query.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    setSearched(true);
    try {
      const data = await api.search(query);
      setResults(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const initial = searchParams.get("q");
    if (initial) {
      setQ(initial);
      runSearch(initial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Find anything</span>
        <h1>Search<span className="heading-period">.</span></h1>
        <p>Full-text search across filenames, auto-generated tags, and video transcripts.</p>
      </div>

      <form
        className="search-bar"
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(q);
        }}
      >
        <input
          type="text"
          placeholder="Search for a word, tag, or something said in a video…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <button className="btn btn-primary" type="submit">
          <SearchIcon size={16} /> Search
        </button>
      </form>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="search-result">
              <Skeleton style={{ width: 56, height: 56, borderRadius: 10, flexShrink: 0 }} />
              <div className="search-result-main" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <Skeleton style={{ height: 12, width: "50%" }} />
                <Skeleton style={{ height: 11, width: "80%" }} />
              </div>
            </div>
          ))}
        </div>
      ) : searched && results.length === 0 ? (
        <div className="empty-state">No matches for “{q}”.</div>
      ) : (
        results.map((r, i) => (
          <div
            key={`${r.media_id}-${i}`}
            className="search-result"
            onClick={() =>
              navigate(
                r.segment_start !== null ? `/media/${r.media_id}?t=${r.segment_start}` : `/media/${r.media_id}`
              )
            }
          >
            {r.thumb_url ? (
              <img className="search-result-thumb" src={withAuth(r.thumb_url)} alt="" />
            ) : (
              <div className="search-result-thumb" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                {r.media_type === "video" ? <Video size={20} /> : <ImageIcon size={20} />}
              </div>
            )}
            <div className="search-result-main">
              <div className="search-result-title">
                {r.filename}
                <span className="tag-chip">{r.source}</span>
                {r.segment_start !== null && <span className="tag-chip">@ {r.segment_start.toFixed(1)}s</span>}
              </div>
              <div className="search-result-snippet">{renderSnippet(r.snippet)}</div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
