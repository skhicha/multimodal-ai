import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, RotateCcw, X, CheckCircle2, AlertCircle } from "lucide-react";
import { useUploadStore } from "../lib/UploadStore";
import "./UploadsTray.css";

// Recently-completed items (done or error) stay visible for a little while
// so a "finished while you were on another page" toast-equivalent is seen,
// then get out of the way on their own without needing a click.
const AUTO_DISMISS_AFTER_MS = 15_000;

export function UploadsTray() {
  const { items, retry, dismiss } = useUploadStore();
  const [collapsed, setCollapsed] = useState(false);
  const [, forceTick] = useState(0);

  // Nothing else re-renders this component once an item finishes, so a
  // slow tick keeps the AUTO_DISMISS_AFTER_MS window honest.
  useEffect(() => {
    const interval = setInterval(() => forceTick((n) => n + 1), 2000);
    return () => clearInterval(interval);
  }, []);

  const visible = items.filter((it) => {
    if (it.status !== "done" && it.status !== "error") return true;
    if (!it.finishedAt) return true;
    return Date.now() - it.finishedAt < AUTO_DISMISS_AFTER_MS;
  });

  if (!visible.length) return null;

  const activeCount = visible.filter((it) => it.status === "queued" || it.status === "uploading" || it.status === "processing").length;

  return (
    <div className="uploads-tray">
      <div className="uploads-tray-header" onClick={() => setCollapsed((c) => !c)}>
        <span>
          {activeCount > 0 ? `Uploading ${activeCount} file${activeCount === 1 ? "" : "s"}…` : "Uploads"}
        </span>
        {collapsed ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>
      {!collapsed && (
        <div className="uploads-tray-list">
          {visible.map((it) => (
            <div key={it.id} className="uploads-tray-row">
              <div className="uploads-tray-row-info">
                <div className="uploads-tray-row-name">{it.file.name}</div>
                <div className="uploads-tray-row-status">
                  {it.status === "queued" && "Waiting…"}
                  {it.status === "uploading" && `Uploading… ${it.progress}%`}
                  {it.status === "processing" && "Processing (faces, transcript, tags)…"}
                  {it.status === "done" && "Done"}
                  {it.status === "error" && (it.error || "Upload failed")}
                </div>
                {(it.status === "uploading" || it.status === "queued") && (
                  <div className="uploads-tray-progress-track">
                    <div className="uploads-tray-progress-fill" style={{ width: `${it.status === "uploading" ? it.progress : 0}%` }} />
                  </div>
                )}
              </div>
              {it.status === "done" && <CheckCircle2 size={16} className="uploads-tray-icon-done" />}
              {it.status === "error" && (
                <button className="uploads-tray-action" title="Retry" onClick={() => retry(it.id)}>
                  <RotateCcw size={14} />
                </button>
              )}
              {it.status === "error" && <AlertCircle size={16} className="uploads-tray-icon-error" />}
              {(it.status === "done" || it.status === "error") && (
                <button className="uploads-tray-action" title="Dismiss" onClick={() => dismiss(it.id)}>
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
