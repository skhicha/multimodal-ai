import { useEffect, useState } from "react";
import { Trash2, RotateCcw, XCircle, Video, ImageIcon } from "lucide-react";
import { api, withAuth, type MediaItem } from "../lib/api";
import "./Library.css";

export function TrashPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setItems(await api.listTrash());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const restore = async (id: string) => {
    setBusyId(id);
    try {
      await api.restoreMedia(id);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const purge = async (id: string, filename: string) => {
    if (!window.confirm(`Permanently delete ${filename}? This cannot be undone.`)) return;
    setBusyId(id);
    try {
      await api.purgeMedia(id);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Recently deleted</span>
        <h1>Trash<span className="heading-period">.</span></h1>
        <p>Items you deleted stay here until restored or permanently removed.</p>
      </div>

      {loading ? (
        <div className="empty-state">Loading…</div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <Trash2 size={32} style={{ marginBottom: 10 }} />
          <div>Trash is empty.</div>
        </div>
      ) : (
        <div className="grid grid-cards">
          {items.map((item) => (
            <div key={item.id} className="media-card" style={{ cursor: "default" }}>
              {item.thumb_url ? (
                <img className="media-card-thumb" src={withAuth(item.thumb_url)} alt={item.filename} loading="lazy" />
              ) : (
                <div className="media-card-thumb-placeholder">
                  {item.media_type === "video" ? <Video size={28} /> : <ImageIcon size={28} />}
                </div>
              )}
              <div className="media-card-vignette" aria-hidden="true" />
              <div className="media-card-body">
                <div className="media-card-name" title={item.filename}>
                  {item.filename}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button className="btn btn-sm" disabled={busyId === item.id} onClick={() => restore(item.id)}>
                    <RotateCcw size={13} /> Restore
                  </button>
                  <button
                    className="btn btn-sm btn-danger"
                    disabled={busyId === item.id}
                    onClick={() => purge(item.id, item.filename)}
                  >
                    <XCircle size={13} /> Delete forever
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
