import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { api, getAccessToken, type MediaItem } from "./api";

export type UploadItemStatus = "queued" | "uploading" | "processing" | "done" | "error";

export interface UploadItem {
  id: string;
  file: File;
  progress: number; // 0-100, HTTP upload progress only
  status: UploadItemStatus;
  media?: MediaItem;
  error?: string;
  attempt: number;
  // Set once the item reaches a terminal state, used to age it out of the
  // tray's "recent" list without having to delete it from the queue.
  finishedAt?: number;
}

const MAX_CONCURRENT_UPLOADS = 2;
const MAX_AUTO_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 1500;
const ACCEPTED_EXT = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"];

interface UploadStoreValue {
  items: UploadItem[];
  enqueueFiles: (files: FileList | File[]) => void;
  retry: (id: string) => void;
  dismiss: (id: string) => void;
}

const UploadStoreContext = createContext<UploadStoreValue | null>(null);

/**
 * Global upload queue: mounted once at the App root (see App.tsx) so its
 * state -- and any in-flight XHR uploads -- survive route changes instead
 * of living in the Upload page's local state and being torn down the
 * moment the user navigates away. UploadsTray renders from this same
 * store from anywhere in the app; Upload.tsx is just one place that calls
 * enqueueFiles(). The concurrency limit (MAX_CONCURRENT_UPLOADS) applies
 * only to the HTTP upload itself -- once a file has been accepted by the
 * server, it moves to "processing" (background face/ASR work on the
 * server, tracked by polling) and immediately frees its upload slot.
 */
export function UploadStoreProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const activeCount = useRef(0);
  const itemsRef = useRef<UploadItem[]>([]);
  itemsRef.current = items;

  const updateItem = useCallback((id: string, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }, []);

  const pollStatus = useCallback(
    (id: string, mediaId: string) => {
      const MAX_CONSECUTIVE_POLL_ERRORS = 5;
      let consecutiveErrors = 0;
      const tick = async () => {
        // Stop polling once the item's been dismissed from the tray, OR
        // once there's no authenticated session to poll with (e.g. logged
        // out, idle-timed-out, or revoked from another device while this
        // upload was still processing) -- otherwise this kept retrying
        // forever, every few seconds, indefinitely spamming 401s even
        // long after the user had left the page or signed out.
        if (!itemsRef.current.find((it) => it.id === id)) return;
        if (!getAccessToken()) return;
        try {
          const media = await api.getMedia(mediaId);
          consecutiveErrors = 0;
          if (!itemsRef.current.find((it) => it.id === id)) return; // dismissed mid-request
          if (media.status === "pending" || media.status === "processing") {
            updateItem(id, { media, status: "processing" });
            setTimeout(tick, 3000);
          } else {
            updateItem(id, { media, status: "done", finishedAt: Date.now() });
          }
        } catch (err) {
          consecutiveErrors += 1;
          if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
            updateItem(id, {
              status: "error",
              error: "Lost track of this upload's processing status -- check Library directly.",
              finishedAt: Date.now(),
            });
            return;
          }
          setTimeout(tick, 4000);
        }
      };
      tick();
    },
    [updateItem]
  );

  const runNext = useCallback(() => {
    while (activeCount.current < MAX_CONCURRENT_UPLOADS) {
      const next = itemsRef.current.find((it) => it.status === "queued");
      if (!next) return;
      activeCount.current += 1;
      updateItem(next.id, { status: "uploading", progress: 0 });
      itemsRef.current = itemsRef.current.map((it) => (it.id === next.id ? { ...it, status: "uploading" } : it));

      api
        .uploadMedia(next.file, (pct) => updateItem(next.id, { progress: pct }))
        .then((media) => {
          updateItem(next.id, { media, status: "processing", progress: 100 });
          pollStatus(next.id, media.id);
        })
        .catch((err: Error) => {
          const attempt = next.attempt + 1;
          if (attempt <= MAX_AUTO_RETRIES) {
            // Retry-with-backoff: a transient blip (flaky wifi, server
            // restart mid-upload) shouldn't require the user to notice
            // and click retry themselves.
            setTimeout(() => {
              updateItem(next.id, { status: "queued", attempt });
              // runNext() reads itemsRef synchronously, which is only kept
              // in sync with React state on render -- update it here too,
              // or the retried item is invisible to runNext() and gets
              // stuck "queued" forever (never re-picked-up).
              itemsRef.current = itemsRef.current.map((it) =>
                it.id === next.id ? { ...it, status: "queued", attempt } : it
              );
              runNext();
            }, RETRY_BASE_DELAY_MS * attempt);
            return;
          }
          updateItem(next.id, { status: "error", error: err.message, attempt, finishedAt: Date.now() });
        })
        .finally(() => {
          activeCount.current -= 1;
          runNext();
        });
    }
  }, [pollStatus, updateItem]);

  const enqueueFiles = useCallback(
    (files: FileList | File[]) => {
      const all = Array.from(files);
      if (!all.length) return;
      const accepted: File[] = [];
      const rejected: File[] = [];
      for (const f of all) {
        const ext = "." + f.name.split(".").pop()?.toLowerCase();
        if (ACCEPTED_EXT.includes(ext)) accepted.push(f);
        else rejected.push(f);
      }
      const now = Date.now();
      const acceptedItems: UploadItem[] = accepted.map((file) => ({
        id: `${file.name}-${file.size}-${now}-${Math.random()}`,
        file,
        progress: 0,
        status: "queued",
        attempt: 0,
      }));
      // Unsupported files are surfaced as their own terminal "error" rows
      // instead of being silently dropped from the selection -- the user
      // needs to see exactly which files were skipped and why, especially
      // when they're mixed in with otherwise-valid files in one action.
      const rejectedItems: UploadItem[] = rejected.map((file) => ({
        id: `${file.name}-${file.size}-${now}-${Math.random()}`,
        file,
        progress: 0,
        status: "error",
        attempt: 0,
        error: "Unsupported file type",
        finishedAt: now,
      }));
      const newItems = [...acceptedItems, ...rejectedItems];
      if (!newItems.length) return;
      setItems((prev) => [...prev, ...newItems]);
      itemsRef.current = [...itemsRef.current, ...newItems];
      runNext();
    },
    [runNext]
  );

  const retry = useCallback(
    (id: string) => {
      updateItem(id, { status: "queued", error: undefined, attempt: 0, progress: 0, finishedAt: undefined });
      itemsRef.current = itemsRef.current.map((it) =>
        it.id === id ? { ...it, status: "queued", error: undefined, attempt: 0, progress: 0, finishedAt: undefined } : it
      );
      runNext();
    },
    [runNext, updateItem]
  );

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((it) => it.id !== id));
  }, []);

  return (
    <UploadStoreContext.Provider value={{ items, enqueueFiles, retry, dismiss }}>
      {children}
    </UploadStoreContext.Provider>
  );
}

export function useUploadStore(): UploadStoreValue {
  const ctx = useContext(UploadStoreContext);
  if (!ctx) throw new Error("useUploadStore must be used within an UploadStoreProvider");
  return ctx;
}

export { ACCEPTED_EXT };
