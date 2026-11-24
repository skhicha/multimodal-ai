import { useState, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Video, ImageIcon, Users, Star, Check, Copy } from "lucide-react";
import { api, type MediaItem } from "../lib/api";
import { withAuth } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import "./MediaCard.css";

function formatDate(iso: string): string {
  const d = new Date(iso.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function MediaCard({
  media,
  selectable = false,
  selected = false,
  onToggleSelect,
  onFavoriteChange,
}: {
  media: MediaItem;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: () => void;
  onFavoriteChange?: (isFavorite: boolean) => void;
}) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("media.edit");
  const [favorite, setFavorite] = useState(media.is_favorite);
  const [favBusy, setFavBusy] = useState(false);

  const onCardClick = () => {
    if (selectable) {
      onToggleSelect?.();
      return;
    }
    navigate(`/media/${media.id}`);
  };

  const onToggleFavorite = async (e: MouseEvent) => {
    e.stopPropagation();
    if (favBusy) return;
    const next = !favorite;
    setFavorite(next);
    onFavoriteChange?.(next);
    setFavBusy(true);
    try {
      await api.toggleFavorite(media.id, next);
    } catch {
      setFavorite(!next);
      onFavoriteChange?.(!next);
    } finally {
      setFavBusy(false);
    }
  };

  return (
    <div className={`media-card${selected ? " media-card-selected" : ""}`} onClick={onCardClick}>
      {media.thumb_url ? (
        <img className="media-card-thumb" src={withAuth(media.thumb_url)} alt={media.filename} loading="lazy" />
      ) : (
        <div className="media-card-thumb-placeholder">
          {media.media_type === "video" ? <Video size={28} /> : <ImageIcon size={28} />}
        </div>
      )}
      <div className="media-card-vignette" aria-hidden="true" />

      {selectable ? (
        <div className={`media-card-select-box${selected ? " checked" : ""}`}>{selected && <Check size={14} />}</div>
      ) : canEdit ? (
        <button
          type="button"
          className={`media-card-fav${favorite ? " active" : ""}`}
          onClick={onToggleFavorite}
          aria-label={favorite ? "Remove from favorites" : "Add to favorites"}
        >
          <Star size={16} fill={favorite ? "currentColor" : "none"} />
        </button>
      ) : favorite ? (
        <div className="media-card-fav active" title="Viewers can't change favorites" style={{ pointerEvents: "none" }}>
          <Star size={16} fill="currentColor" />
        </div>
      ) : null}

      <div className="media-card-badge">
        {media.media_type === "video" ? <Video size={12} /> : <ImageIcon size={12} />}
        {media.media_type}
        {media.has_faces && (
          <>
            <Users size={12} style={{ marginLeft: 4 }} />
            {media.face_count}
          </>
        )}
      </div>

      {media.status !== "ready" && (
        <span className={`status-pill ${media.status} media-card-status`}>{media.status}</span>
      )}

      {media.duplicate_count > 0 && (
        <div className="media-card-badge" style={{ top: 34 }} title={`${media.duplicate_count} identical copy(ies) in your vault`}>
          <Copy size={12} /> {media.duplicate_count}
        </div>
      )}

      <div className="media-card-body">
        <div className="media-card-name" title={media.filename}>
          {media.filename}
        </div>
        <div className="media-card-meta">
          {formatDate(media.taken_at || media.created_at)}
          {media.duration_s ? ` · ${media.duration_s.toFixed(1)}s` : ""}
        </div>
        {media.tags.length > 0 && (
          <div className="media-card-tags">
            {media.tags.slice(0, 3).map((t) => (
              <span key={t} className="tag-chip">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
