import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, CheckCircle2, RotateCcw } from "lucide-react";
import { withAuth } from "../lib/api";
import { useUploadStore, ACCEPTED_EXT } from "../lib/UploadStore";
import "./Upload.css";

export function UploadPage() {
  const { items, enqueueFiles, retry } = useUploadStore();
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Uploads are tracked in the global store (UploadStoreProvider, mounted at
  // the app root), not in this page's own state -- they keep running, and
  // the floating UploadsTray keeps showing them, regardless of which page
  // is open. So once files are queued there's nothing left for the user to
  // watch here that the tray doesn't already show from anywhere else in the
  // app, and heading straight to Library (where the new items will appear
  // as they finish processing) is more useful than staying on this page.
  const enqueueAndGoToLibrary = (files: FileList) => {
    enqueueFiles(files);
    navigate("/library");
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Add to the vault</span>
        <h1>Upload media<span className="heading-period">.</span></h1>
        <p>
          Drop in photos or videos. MemoryLens AI processes them in the background — faces, transcripts,
          EXIF/GPS, and tags. Uploads keep going (and a tray in the corner keeps tracking them) even if you
          navigate away from this page.
        </p>
      </div>

      <div
        className={`dropzone glass-card${dragActive ? " active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (e.dataTransfer.files.length) enqueueAndGoToLibrary(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <div className="dropzone-icon">
          <UploadCloud size={26} />
        </div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Drag & drop files here, or click to browse</div>
        <div style={{ fontSize: 13 }}>JPG, PNG, WEBP, HEIC · MP4, MOV, MKV, WEBM — select or drop multiple at once</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXT.join(",")}
          style={{ display: "none" }}
          onChange={(e) => e.target.files && enqueueAndGoToLibrary(e.target.files)}
        />
      </div>

      {items.length > 0 && (
        <div className="upload-list">
          {items.map((row) => (
            <div key={row.id} className="upload-row">
              {row.media?.thumb_url ? (
                <img className="upload-row-thumb" src={withAuth(row.media.thumb_url)} alt="" />
              ) : (
                <div className="upload-row-thumb" />
              )}
              <div className="upload-row-info">
                <div className="upload-row-name">{row.file.name}</div>
                {row.status === "error" ? (
                  <div style={{ color: "var(--danger)", fontSize: 12.5, display: "flex", alignItems: "center", gap: 8 }}>
                    {row.error}
                    <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => retry(row.id)}>
                      <RotateCcw size={12} style={{ verticalAlign: -1, marginRight: 4 }} />
                      Retry
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="upload-progress-track">
                      <div
                        className="upload-progress-fill"
                        style={{ width: `${row.status === "uploading" ? row.progress : row.status === "queued" ? 0 : 100}%` }}
                      />
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                      {row.status === "queued" && "Waiting in queue…"}
                      {row.status === "uploading" && `Uploading… ${row.progress}%`}
                      {row.status === "processing" && `Status: ${row.media?.status ?? "processing"}`}
                      {row.status === "done" && `Status: ${row.media?.status ?? "ready"}`}
                    </div>
                  </>
                )}
              </div>
              {row.media?.status === "ready" ? (
                <CheckCircle2 size={20} className="upload-row-done" />
              ) : (
                row.media && <span className={`status-pill ${row.media.status}`}>{row.media.status}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
