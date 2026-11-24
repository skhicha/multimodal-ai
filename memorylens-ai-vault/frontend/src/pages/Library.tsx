import { useEffect, useMemo, useState } from "react";
import { ImageOff, CheckSquare, Trash2, X, FolderPlus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, getAccessToken, type MediaItem, type MediaType } from "../lib/api";
import { MediaCard } from "../components/MediaCard";
import { LibrarySkeletonGrid } from "../components/Skeleton";
import { useAuth } from "../lib/AuthContext";
import { useUploadStore } from "../lib/UploadStore";
import "./Library.css";

export function LibraryPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canEdit = hasPermission("media.delete");
  const canSaveCollection = hasPermission("collections.create");
  const [savingCollection, setSavingCollection] = useState(false);
  const { items: uploadItems } = useUploadStore();
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [mediaType, setMediaType] = useState<MediaType | "">("");
  const [tag, setTag] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.listMedia({
        media_type: mediaType || undefined,
        tag: tag || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setItems(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mediaType, tag, dateFrom, dateTo]);

  // A brand-new upload (e.g. the one that just redirected here from the
  // Upload page) has no row in `items` at all yet -- its server-side
  // media row may not even exist the instant this page mounts, since the
  // multipart upload itself is still in flight via the global upload
  // queue. The "poll while something already in `items` is unsettled"
  // effect below can't catch that: an item Library has never fetched
  // can't be in `items` to begin with, so nothing would ever trigger a
  // refetch until the user manually reloads. Watching the global upload
  // store directly -- which knows about every in-flight upload from
  // anywhere in the app, not just ones already reflected here -- closes
  // that gap: any change in what it's tracking (a new file queued, one
  // finishing the HTTP upload and becoming a real server row, one
  // finishing processing) triggers an immediate refetch.
  const uploadActivitySignal = uploadItems.map((it) => `${it.id}:${it.status}`).join(",");
  useEffect(() => {
    if (!uploadItems.length) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadActivitySignal]);

  // Media that was already "pending"/"processing" when this page loaded
  // (including right after a full browser refresh, which always kills any
  // literally-mid-HTTP-request upload but never the server-side row it
  // already created) needs its own refetch loop -- otherwise its status
  // pill would stay stuck until the user manually refreshes again.
  useEffect(() => {
    const hasUnsettled = items.some((i) => i.status !== "ready" && i.status !== "failed");
    if (!hasUnsettled) return;
    const interval = setInterval(() => {
      // Stop silently once there's no session left to poll with (logged
      // out, idle-timed-out, or revoked elsewhere while this page sat on
      // unsettled media) -- otherwise this kept retrying every 4s forever,
      // throwing an unhandled rejection each time with no way to stop.
      if (!getAccessToken()) {
        clearInterval(interval);
        return;
      }
      load().catch(() => {
        // A single failed refresh isn't fatal -- the next tick retries.
        // If the session is actually gone, the getAccessToken() check
        // above will stop the interval on the next tick.
      });
    }, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    items.forEach((i) => i.tags.forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [items]);

  const visibleItems = useMemo(
    () => (favoritesOnly ? items.filter((i) => i.is_favorite) : items),
    [items, favoritesOnly]
  );

  const toggleSelectMode = () => {
    setSelectMode((s) => !s);
    setSelected(new Set());
  };

  const toggleSelected = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const deleteSelected = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} selected item(s)? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await Promise.all(Array.from(selected).map((id) => api.deleteMedia(id)));
      setSelected(new Set());
      setSelectMode(false);
      await load();
    } finally {
      setDeleting(false);
    }
  };

  const onFavoriteChange = (id: string, is_favorite: boolean) => {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, is_favorite } : i)));
  };

  const saveAsCollection = async () => {
    const name = window.prompt("Name this smart collection (it will always follow the current filters):");
    if (!name || !name.trim()) return;
    setSavingCollection(true);
    try {
      const created = await api.createCollection({
        name: name.trim(),
        filter: {
          media_type: mediaType || undefined,
          tag: tag || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        },
      });
      navigate(`/collections/${created.id}`);
    } finally {
      setSavingCollection(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Your collection</span>
        <h1>Library<span className="heading-period">.</span></h1>
        <p>Every photo and video in your vault, with filters for type, tag, and date.</p>
      </div>

      <div className="library-filters">
        <select value={mediaType} onChange={(e) => setMediaType(e.target.value as MediaType | "")}>
          <option value="">All types</option>
          <option value="photo">Photos</option>
          <option value="video">Videos</option>
        </select>
        <select value={tag} onChange={(e) => setTag(e.target.value)}>
          <option value="">All tags</option>
          {allTags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <button
          type="button"
          className={`btn btn-sm${favoritesOnly ? " btn-primary" : ""}`}
          onClick={() => setFavoritesOnly((v) => !v)}
        >
          Favorites
        </button>
        {canEdit && (
          <button type="button" className={`btn btn-sm${selectMode ? " btn-primary" : ""}`} onClick={toggleSelectMode}>
            <CheckSquare size={14} /> {selectMode ? "Cancel select" : "Select"}
          </button>
        )}
        {canSaveCollection && (
          <button type="button" className="btn btn-sm" disabled={savingCollection} onClick={saveAsCollection}>
            <FolderPlus size={14} /> Save as collection
          </button>
        )}
      </div>

      {selectMode && (
        <div className="library-select-toolbar glass-card">
          <span>{selected.size} selected</span>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-sm" onClick={() => setSelected(new Set())} disabled={selected.size === 0}>
              <X size={14} /> Clear
            </button>
            <button
              className="btn btn-sm btn-danger"
              onClick={deleteSelected}
              disabled={selected.size === 0 || deleting}
            >
              <Trash2 size={14} /> {deleting ? "Deleting…" : "Delete selected"}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <LibrarySkeletonGrid />
      ) : visibleItems.length === 0 ? (
        <div className="empty-state">
          <ImageOff size={32} style={{ marginBottom: 10 }} />
          <div>No media matches these filters yet. Try uploading something first.</div>
        </div>
      ) : (
        <div className="grid grid-cards">
          {visibleItems.map((item) => (
            <MediaCard
              key={item.id}
              media={item}
              selectable={selectMode}
              selected={selected.has(item.id)}
              onToggleSelect={() => toggleSelected(item.id)}
              onFavoriteChange={(fav) => onFavoriteChange(item.id, fav)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
