import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "../lib/leafletIcons";
import { api, withAuth, type MediaItem } from "../lib/api";

// A marker representing a count badge for 2+ items sharing (effectively)
// the same coordinates -- a simple colored circle with the number in it,
// built from an inline SVG data URI so no extra asset/icon file is needed.
function countIcon(count: number) {
  const size = 34;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
    <circle cx="${size / 2}" cy="${size / 2}" r="${size / 2 - 2}" fill="#a8431f" stroke="white" stroke-width="2" />
    <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="700" fill="white">${count}</text>
  </svg>`;
  return L.icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(svg)}`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

export function MapViewPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.listMedia().then((data) => setItems(data.filter((m) => m.gps_lat != null && m.gps_lon != null)));
  }, []);

  // Multiple photos/videos taken at (or extremely near) the exact same spot
  // -- e.g. several shots in one place within minutes of each other -- is a
  // completely normal case, not an edge case, so it's handled as one group
  // per effective location (rounded to ~1 metre) rather than rendering one
  // Leaflet marker per item: at any zoom level where two locations would
  // visually overlap anyway, a stack of identical pins is not actually more
  // informative than a single pin with a count and a popup listing every
  // item at that spot.
  const groups = useMemo(() => {
    const byKey = new Map<string, MediaItem[]>();
    for (const item of items) {
      const key = `${(item.gps_lat as number).toFixed(5)},${(item.gps_lon as number).toFixed(5)}`;
      const list = byKey.get(key);
      if (list) list.push(item);
      else byKey.set(key, [item]);
    }
    return Array.from(byKey.values());
  }, [items]);

  const center: [number, number] = items.length
    ? [items[0].gps_lat as number, items[0].gps_lon as number]
    : [20, 0];

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Where it happened</span>
        <h1>Map<span className="heading-period">.</span></h1>
        <p>Photos and videos with GPS data in their EXIF metadata, plotted by location.</p>
      </div>

      {items.length === 0 ? (
        <div className="empty-state glass-card">
          No geotagged media yet. Photos with GPS EXIF data (most phone cameras include it) will show up here.
        </div>
      ) : (
        <div className="glass-card" style={{ height: "70vh", overflow: "hidden" }}>
          <MapContainer center={center} zoom={groups.length === 1 ? 12 : 3} style={{ height: "100%", width: "100%" }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
            {groups.map((group) => {
              const [first] = group;
              const position: [number, number] = [first.gps_lat as number, first.gps_lon as number];
              return (
                <Marker
                  key={first.id}
                  position={position}
                  icon={group.length > 1 ? countIcon(group.length) : undefined}
                >
                  <Popup>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                        maxHeight: 280,
                        overflowY: "auto",
                        minWidth: 160,
                      }}
                    >
                      {group.length > 1 && (
                        <strong style={{ fontSize: 12.5 }}>{group.length} items at this location</strong>
                      )}
                      {group.map((item) => (
                        <div key={item.id} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          {item.thumb_url && (
                            <img
                              src={withAuth(item.thumb_url)}
                              alt={item.filename}
                              style={{ width: 160, borderRadius: 6 }}
                            />
                          )}
                          <strong style={{ fontSize: 12, wordBreak: "break-all" }}>{item.filename}</strong>
                          <button className="btn" onClick={() => navigate(`/media/${item.id}`)}>
                            Open
                          </button>
                        </div>
                      ))}
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>
      )}
    </div>
  );
}
