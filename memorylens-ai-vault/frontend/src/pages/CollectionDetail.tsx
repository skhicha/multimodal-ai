import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ImageOff } from "lucide-react";
import { api, type Collection, type MediaItem } from "../lib/api";
import { MediaCard } from "../components/MediaCard";
import "./Library.css";

export function CollectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([api.getCollection(id), api.listCollectionItems(id)])
      .then(([c, i]) => {
        setCollection(c);
        setItems(i);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="empty-state">Loading…</div>;
  if (!collection) return <div className="empty-state">Collection not found.</div>;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button className="btn" onClick={() => navigate("/collections")}>
          <ArrowLeft size={16} /> Back
        </button>
        <h1 style={{ fontSize: 20, margin: 0 }}>{collection.name}</h1>
      </div>
      <p style={{ color: "var(--text-muted)", marginTop: -10 }}>
        {items.length} item{items.length === 1 ? "" : "s"} {collection.is_smart ? "· follows a saved filter automatically" : ""}
      </p>

      {items.length === 0 ? (
        <div className="empty-state">
          <ImageOff size={32} style={{ marginBottom: 10 }} />
          <div>Nothing in this collection yet.</div>
        </div>
      ) : (
        <div className="grid grid-cards">
          {items.map((item) => (
            <MediaCard key={item.id} media={item} />
          ))}
        </div>
      )}
    </div>
  );
}
