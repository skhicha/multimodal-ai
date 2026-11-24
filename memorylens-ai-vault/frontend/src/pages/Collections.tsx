import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderPlus, Sparkles, Folder, Trash2 } from "lucide-react";
import { api, type Collection } from "../lib/api";
import "./Library.css";

export function CollectionsPage() {
  const navigate = useNavigate();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setCollections(await api.listCollections());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await api.createCollection({ name: name.trim() });
      setName("");
      await load();
    } finally {
      setCreating(false);
    }
  };

  const remove = async (id: string, collectionName: string) => {
    if (!window.confirm(`Delete collection "${collectionName}"? Its media stays in your Library.`)) return;
    await api.deleteCollection(id);
    await load();
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Albums</span>
        <h1>Collections<span className="heading-period">.</span></h1>
        <p>Group media into albums -- manual picks, or "smart" collections that follow a filter automatically.</p>
      </div>

      <div className="library-filters">
        <input
          type="text"
          placeholder="New collection name…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create()}
          style={{ minWidth: 220 }}
        />
        <button className="btn btn-sm btn-primary" disabled={creating || !name.trim()} onClick={create}>
          <FolderPlus size={14} /> Create
        </button>
      </div>

      {loading ? (
        <div className="empty-state">Loading…</div>
      ) : collections.length === 0 ? (
        <div className="empty-state">
          <Folder size={32} style={{ marginBottom: 10 }} />
          <div>No collections yet. Create one above, or save a Library filter as a smart collection.</div>
        </div>
      ) : (
        <div className="grid grid-cards">
          {collections.map((c) => (
            <div
              key={c.id}
              className="media-card"
              style={{ cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", minHeight: 140 }}
              onClick={() => navigate(`/collections/${c.id}`)}
            >
              <div className="media-card-body" style={{ textAlign: "center" }}>
                {c.is_smart ? <Sparkles size={22} style={{ marginBottom: 6 }} /> : <Folder size={22} style={{ marginBottom: 6 }} />}
                <div className="media-card-name">{c.name}</div>
                <div className="media-card-meta">
                  {c.item_count} item{c.item_count === 1 ? "" : "s"} {c.is_smart ? "· smart" : ""}
                </div>
                <button
                  className="btn btn-sm btn-danger"
                  style={{ marginTop: 8 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(c.id, c.name);
                  }}
                >
                  <Trash2 size={13} /> Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
