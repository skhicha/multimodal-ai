import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type DashboardSummary } from "../lib/api";
import { useCountUp } from "../lib/useCountUp";
import { StatTileSkeleton } from "../components/Skeleton";
import "./Dashboard.css";

const COLORS = ["#a8431f", "#7a9b6e", "#c98f3a", "#8a6a9e", "#d19a6a", "#6b8a7a"];

function StatCard({ value, label }: { value: number; label: string }) {
  const display = useCountUp(value);
  return (
    <div className="glass-card stat-card">
      <div className="stat-value">{display}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    api.dashboardSummary().then(setSummary);
  }, []);

  if (!summary) {
    return (
      <div>
        <div className="page-header">
          <span className="eyebrow">Welcome back</span>
          <h1>Dashboard<span className="heading-period">.</span></h1>
          <p>An overview of what's in your vault.</p>
        </div>
        <div className="stat-grid">
          {Array.from({ length: 5 }).map((_, i) => (
            <StatTileSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Welcome back</span>
        <h1>Dashboard<span className="heading-period">.</span></h1>
        <p>An overview of what's in your vault.</p>
      </div>

      <div className="stat-grid">
        <StatCard value={summary.total_media} label="Total media" />
        <StatCard value={summary.total_photos} label="Photos" />
        <StatCard value={summary.total_videos} label="Videos" />
        <StatCard value={summary.total_faces} label="Faces detected" />
        <StatCard value={summary.total_with_gps} label="Geotagged items" />
      </div>

      {summary.is_admin && (
        <div className="glass-card" style={{ padding: 20, marginBottom: 24 }}>
          <h3 style={{ marginTop: 0 }}>System-wide (admin only)</h3>
          <div className="stat-grid">
            <StatCard value={summary.system_total_users ?? 0} label="Total users" />
            <StatCard value={summary.system_total_media ?? 0} label="Total media (all users)" />
          </div>
        </div>
      )}

      <div className="chart-grid">
        <div className="glass-card chart-card">
          <h3>Uploads over time</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={summary.uploads_by_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" />
              <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={11} />
              <YAxis allowDecimals={false} stroke="var(--text-muted)" fontSize={11} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#a8431f" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-card chart-card">
          <h3>Photo vs video split</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={summary.type_split}
                dataKey="count"
                nameKey="media_type"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
              >
                {summary.type_split.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-card chart-card">
          <h3>Tag distribution</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={summary.tag_distribution} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" />
              <XAxis type="number" allowDecimals={false} stroke="var(--text-muted)" fontSize={11} />
              <YAxis type="category" dataKey="tag" width={110} stroke="var(--text-muted)" fontSize={11} />
              <Tooltip />
              <Bar dataKey="count" fill="#7a9b6e" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-card chart-card">
          <h3>Map hotspot summary</h3>
          {summary.map_hotspots.length === 0 ? (
            <div className="empty-state" style={{ padding: "30px 0" }}>
              No geotagged media yet.
            </div>
          ) : (
            <div style={{ maxHeight: 240, overflowY: "auto" }}>
              {summary.map_hotspots.map((h) => (
                <div
                  key={h.media_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "8px 4px",
                    borderBottom: "1px solid var(--surface-border)",
                    fontSize: 13,
                  }}
                >
                  <span>{h.filename}</span>
                  <span style={{ color: "var(--text-muted)" }}>
                    {h.lat.toFixed(3)}, {h.lon.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
