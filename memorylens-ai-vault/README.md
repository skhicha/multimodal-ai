# MemoryLens AI

A personal AI media vault: upload your own photos and videos, let a small local
pipeline auto-process them (face detection, audio transcription, AI visual
scene captioning, EXIF/GPS extraction, auto-tagging, duplicate detection),
then organize them into albums, browse a timeline, see photos on a map,
full-text search everything, and chat with an "Ask AI" assistant that answers
with citations back to your own media. Multi-role access control (admin /
editor / viewer), session security (idle timeout, cross-device logout, email
OTP, authenticator-app 2FA), and a Trash/restore flow round it out.

This is a **practice/capstone project**, built as a lighter, fully local
re-implementation of concepts from a larger video-forensics internship
project (FastAPI + React/TS + OpenCV + ASR + SQL full-text search + RAG). It
is a separate, from-scratch codebase — see `docs/PRESENTATION_GUIDE.md` for
how the two relate and why things were simplified the way they were.

Runs entirely on a laptop. No GPU, no Docker, no cloud account required —
Ask AI defaults to an offline extractive answer, and can optionally be
upgraded to a real LLM via a local Ollama model (free, no API key) or a
cloud provider (Anthropic/Gemini/OpenAI).

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Database | SQLite (stdlib `sqlite3`, no ORM) + FTS5 full-text search |
| Computer vision | OpenCV (Haar cascade face detection, keyframe extraction) |
| Speech-to-text | faster-whisper (CPU, "small" model by default) |
| Scene captioning | BLIP image-captioning model (CPU-only torch) — what a photo/keyframe visually shows, distinct from speech transcription |
| Photo metadata | Pillow EXIF (GPS, timestamp, camera model) |
| Video metadata | `ffprobe` subprocess, falls back to OpenCV if ffmpeg isn't installed |
| Dedupe | SHA-256 content hash per upload, per-user |
| Ask AI (RAG) | FTS5 retrieval (filenames/tags/transcripts/captions) + pluggable LLM: `mock`, `anthropic`, `gemini`, `openai`, or `ollama` (local, no API key) |
| Auth & sessions | JWT access + httpOnly refresh cookie, revocable DB-backed sessions, Server-Sent Events for live cross-device logout, email OTP, authenticator-app TOTP 2FA |
| RBAC | Database-backed roles/permissions (admin/editor/viewer), runtime-editable, not hard-coded |
| Frontend | React 18 + TypeScript + Vite |
| UI | Plain CSS with variables (dark/light theme), Radix UI primitives, lucide-react icons |
| Charts | Recharts |
| Map | Leaflet + react-leaflet |

## Project layout

```
backend/
  app/
    main.py            FastAPI app, CORS, security headers, router wiring
    db.py               SQLite schema + RBAC seeding + connection helpers (FTS5 included)
    auth.py             JWT verification, require_permission() dependency
    services/
      vision.py          Face detection, keyframes, thumbnails, video probing
      asr.py              faster-whisper transcription (graceful fallback)
      captioning.py       BLIP visual scene captioning (graceful fallback)
      exif.py             Pillow EXIF/GPS extraction
      pipeline.py         Background processing orchestration + tagging
      search.py           FTS5 indexing + querying (filenames/tags/transcripts/captions)
      ask_ai.py           RAG retrieval + mock/anthropic/gemini/openai/ollama generation
      sessions.py         Revocable sessions, SSE tickets
      mfa.py              TOTP authenticator-app 2FA
      otp.py              Email one-time-code generation/verification
      mailer.py           SMTP send, dev-mode console fallback
    routers/
      auth.py, media.py, search.py, ask.py, dashboard.py, admin.py, collections.py
  requirements.txt
  .env.example
  run.sh                 venv + install + uvicorn on :8000
frontend/
  src/
    pages/               Upload, Library, MediaDetail, Collections, CollectionDetail,
                          Trash, Timeline, MapView, Search, AskAI, Dashboard, Settings, Admin
    components/          Navbar, ThemeToggle, MediaCard, FaceBoxOverlay, ChatBubble,
                          UploadsTray
    lib/                 api.ts (typed fetch client), AuthContext.tsx, UploadStore.tsx
  vite.config.ts          dev proxy: /api -> http://localhost:8000
docs/
  PRESENTATION_GUIDE.md   elevator pitch, architecture, walkthrough script, Q&A
  TESTING_GUIDE.md        full manual test pass + live demo script
  MemoryLens_AI_Demo.mp4  recorded end-to-end walkthrough of every feature
```

## Running it locally (two terminals)

### 1. Backend

```bash
cd backend
./run.sh
```

`run.sh` creates a venv (first run only), installs `requirements.txt`, copies
`.env.example` to `.env` if missing, and starts Uvicorn on
**http://localhost:8000**. API docs: http://localhost:8000/docs

Or do it by hand:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies all `/api/*` requests to the
backend on :8000, so no CORS wrangling is needed in dev.

### First run: create an account

MemoryLens AI is multi-user: every item belongs to a signed-in account, and
each account only ever sees its own media. On first run, open
**http://localhost:5173/register** and create an account (email + password +
display name) before uploading anything — you'll be redirected there
automatically if you try to use the app signed out.

## Authentication, sessions, and RBAC

- **Registration / login**: `POST /api/auth/register` and `POST
  /api/auth/login` validate the email format and a password policy (min 8
  characters, at least one letter and one digit), hash passwords with
  **bcrypt** (via `passlib`), and never store or log plaintext passwords.
  The very first account ever created becomes **admin** automatically;
  every account after that defaults to **editor**.
- **Tokens**: on success the API returns a short-lived **JWT access token**
  (HS256, signed with `JWT_SECRET` — the app refuses to start without an
  explicit one) in the JSON response body, and sets a longer-lived
  **refresh token** as an **httpOnly cookie** — JavaScript never touches
  the refresh token directly, which keeps it safe from XSS.
- **Using the API**: the frontend sends `Authorization: Bearer <access
  token>` on every request. When an access token expires, the fetch
  wrapper in `frontend/src/lib/api.ts` transparently calls `POST
  /api/auth/refresh` (which reads the refresh cookie) to get a new
  access/refresh pair, then retries the original request once — the user
  never notices.
- **Sessions & cross-device logout**: each login creates a revocable row in
  a `sessions` table (not a bare stateless token). Settings → Sessions lists
  every active session with a device label; "Log out all other devices" (or
  an admin deactivating the account) pushes an instant logout to every
  other open tab via Server-Sent Events, authenticated with a short-lived,
  single-use connection ticket rather than the access token in the URL.
- **Idle timeout**: 15 minutes of inactivity triggers a 60-second warning,
  then an automatic logout with a clear "signed out due to inactivity"
  message.
- **Email OTP**: Settings lets a user require a one-time emailed code on
  every future login, on top of the password. In dev (no `SMTP_HOST`
  configured, or delivery fails), the code is printed to the backend
  console instead of silently vanishing.
- **Authenticator-app 2FA (TOTP)**: real, offline-capable two-factor
  authentication — Settings → "Set up" generates a QR code and secret via
  `pyotp`, confirmed with a 6-digit code, with backup codes issued on
  enable and a password-gated disable flow.
- **RBAC**: three roles — **admin**, **editor**, **viewer** — each mapped to
  a configurable subset of permission codes (media, search, ask_ai,
  dashboard, settings, users, roles, collections) stored in the database
  and editable live from the Admin → Roles & Permissions panel. Every
  protected route checks the database via a `require_permission()`
  dependency on each request, not a cached flag from login, so a
  permission change takes effect immediately — even for a token issued
  before the change. A guard independently blocks removing
  `users.*`/`roles.*` from the admin role, so no one can lock every admin
  out by accident.
- **Data isolation**: every `media`/search/dashboard/ask/collections query
  is scoped to `user_id = <current user>` at the SQL level — one account
  can never read another account's uploads, thumbnails, search results,
  collections, or Ask AI citations.
- **Rate limiting**: `/api/auth/login` and `/api/auth/register` are limited
  to 5 requests/minute per IP (via `slowapi`) to blunt brute-force/credential
  stuffing attempts.

## Collections, Trash, and duplicate detection

- **Collections (albums)**: group media into a **manual** album (explicit
  add/remove) or a **smart** album that stores a filter (media type, tag,
  date range) and re-resolves its membership live against the vault on
  every view — never a stale snapshot from when it was created.
- **Trash**: deleting an item soft-deletes it (removed from search
  immediately, but recoverable) rather than destroying it. Trash offers
  **Restore** (puts it back, re-indexes it) and **Delete forever** (the
  one genuinely irreversible action, only reachable from Trash).
- **Duplicate detection**: every upload is hashed (SHA-256); a repeated
  upload is still accepted (never blocked) but flagged with a visible
  "N identical copies" badge in Library and Media Detail.

## Notes on the processing pipeline

- Uploads are saved immediately and processed in a background thread per
  item (`status`: `pending` → `processing` → `ready`/`failed`). The frontend
  polls `/api/media/{id}` until it settles.
- **Photos**: EXIF (GPS/timestamp/camera) via Pillow, Haar-cascade face
  detection + thumbnail via OpenCV, simple brightness/saturation heuristics
  for "day/night" and "likely indoor/outdoor" tags (explicitly labelled as
  guesses, not claimed ML).
- **Videos**: `ffprobe` (falls back to OpenCV automatically if `ffmpeg`
  isn't installed) for duration/fps/resolution, one keyframe every ~2s with
  face boxes drawn in, and faster-whisper transcription.
- **Whisper / ASR**: the first time a video is processed, faster-whisper
  downloads its model weights from Hugging Face — this needs internet
  access **once**. After that it's cached locally (`~/.cache/huggingface`)
  and works fully offline. If the download fails, or the machine has no
  usable audio track, or anything else goes wrong, the ASR step is marked
  `skipped` and the rest of the pipeline (keyframes, tags, metadata)
  continues normally — a single step failing never fails the whole upload.
- **Scene captioning**: every photo, and up to 3 sampled keyframes per
  video, get a one-sentence visual description from a BLIP captioning
  model — what the image *shows*, independent of and complementary to the
  transcript's *what was said*. Runs on CPU, beam search + a repetition
  penalty (plain greedy decoding produced artifacts like "a beard and a
  beard" on real test photos). Best-effort: a model load or inference
  failure is caught, logged, and skipped without failing the upload.
- Every processed item (filename + tags + transcript segments + scene
  captions) gets indexed into a SQLite FTS5 table, which backs both
  `/api/search` and the retrieval step of `/api/ask` — so Ask AI can
  answer purely visual questions ("is there a vehicle in my videos?") even
  when nothing was ever spoken or typed.

## Switching Ask AI's answer provider

By default `LLM_PROVIDER=mock` in `backend/.env`: the Ask AI assistant
retrieves matching citations via full-text search and builds a plainly
labelled **"[Offline mode / mock provider]"** answer that only repeats what
was actually retrieved — it never fabricates facts.

To get fluent, synthesized answers over the same citations, pick any one
provider:

```bash
# backend/.env — pick ONE
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

LLM_PROVIDER=gemini
GEMINI_API_KEY=...

LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

LLM_PROVIDER=ollama      # local Llama 3.1 8B via Ollama — no API key, no cost, no quota
OLLAMA_HOST=http://localhost:11434
```

Restart the backend after editing `.env`. The Settings page shows which
provider is currently active, and any provider error falls back
automatically to the offline `mock` answer rather than breaking the chat.

## Known simplifications (honest, on purpose)

- Face detection uses OpenCV's classic Haar cascade, not a deep face
  recognizer — it finds faces, it doesn't identify *who* they are.
- "Outdoor"/"time of day" tags are brightness/saturation heuristics, not a
  trained scene classifier. They're labelled as guesses in the UI.
- No background job queue (Celery/Redis/etc.) — a plain daemon thread per
  upload, which is appropriate at personal-vault scale and keeps the setup
  Docker-free.
- SQLite, not Postgres — fine for a single-user local app, and FTS5 gives
  the same full-text search capability without an extra service to run.
- No refresh-token rotation/blacklist and no OAuth/SSO beyond the optional
  Google sign-in button — email/password plus the session table above is
  enough to demonstrate real authentication and per-user isolation without
  building a full identity platform. (Password reset and email
  verification *are* implemented — see Authentication above.)
- The cross-device logout push runs through an in-memory, single-process
  broker; a real multi-instance deployment would need something shared
  like Redis pub/sub instead.
- Scene captioning is CPU-only and takes a few seconds per image, so a
  large batch upload on a slow machine could make captioning the
  bottleneck in the background pipeline — it fails safe, but hasn't been
  load-tested at high volume.
- The dev SQLite database was reset (not migrated) when the `users` table
  and `media.user_id` column were added, since it only ever held
  throwaway local test uploads with no real users attached.
