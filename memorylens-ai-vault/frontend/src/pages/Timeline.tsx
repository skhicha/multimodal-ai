import { useEffect, useState } from "react";
import { api, type MediaItem } from "../lib/api";
import { MediaCard } from "../components/MediaCard";
import "./Timeline.css";

function dateKey(iso: string): string {
  return iso.slice(0, 10);
}

function formatHeading(key: string): string {
  const d = new Date(`${key}T00:00:00`);
  if (Number.isNaN(d.getTime())) return key;
  return d.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

export function TimelinePage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listMedia().then((data) => {
      setItems(data);
      setLoading(false);
    });
  }, []);

  const groups = new Map<string, MediaItem[]>();
  for (const item of items) {
    const key = dateKey(item.created_at);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  const sortedKeys = Array.from(groups.keys()).sort((a, b) => b.localeCompare(a));

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Day by day</span>
        <h1>Timeline<span className="heading-period">.</span></h1>
        <p>Your vault, grouped by the day each item was added.</p>
      </div>

      {loading ? (
        <div className="empty-state">Loading…</div>
      ) : sortedKeys.length === 0 ? (
        <div className="empty-state">Nothing uploaded yet.</div>
      ) : (
        sortedKeys.map((key) => (
          <div className="timeline-group" key={key}>
            <div className="timeline-date">
              {formatHeading(key)}
              <span className="count">{groups.get(key)!.length} item(s)</span>
              <div className="timeline-line" />
            </div>
            <div className="grid grid-cards">
              {groups.get(key)!.map((item) => (
                <MediaCard key={item.id} media={item} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
