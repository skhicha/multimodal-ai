# SonaVault

Full-Stack Acoustic Intelligence Platform for NVIDIA DGX Spark (GB10 Grace-Blackwell).

SonaVault is a sovereign, 100%-open-source-model platform for **Multilingual Acoustic
Soundscape, Field-Dispatch, and Regulatory Dossier Intelligence** — built for coastal
marine sanctuary monitoring, maritime incident coordination, and archival bioacoustic
research. It is strictly non-visual: zero camera frames, zero raster images. All data
is passive hydrophone audio, multilingual spoken field dispatches, and structured
regulatory documents (PDF/DOCX/NOAA XML).

See [`docs/`](docs/) for the full architecture blueprint this repo implements.

## Architecture at a glance

- **Backend**: FastAPI vertical-slice monolith (`apps/api`) + RQ workers, Postgres 16,
  Qdrant (hybrid RRF search), Redis.
- **GPU sidecars** (`services/`): `speech-audio-gpu` (Whisper, pyannote diarization,
  AST, CLAP) and `nlp-retrieval-gpu` (BGE-M3, BGE-reranker, GLiNER, MADLAD-400), plus
  `vllm-moe-gpu` (Qwen3-30B-A3B-NVFP4) for RAG briefing synthesis.
- **Frontend**: React 18 + Vite + TypeScript SPA (`apps/web`), per-feature vertical
  slices, Leaflet map, hls.js live hydrophone audio, Recharts.
- **Streaming**: MediaMTX audio-only Low-Latency HLS (AAC-LC).
- **Security**: Argon2id passwords, mandatory phishing-resistant MFA (WebAuthn Passkeys
  + TOTP + recovery codes) for privileged roles, 5-tier RBAC with sanctuary scoping,
  AES-256-GCM envelope encryption + HMAC blind indexing for PII, append-only
  OAIS/PREMIS provenance hash chain.

## Build status

This repo is being built incrementally per the 4-sprint plan in the architecture
blueprint:

- [x] Sprint 0 — Monorepo scaffold
- [x] Sprint 1 — Auth, MFA, Security & Core Monolith
- [ ] Sprint 2 — GPU Sidecars, MediaMTX & 7-Stage Pipeline
- [ ] Sprint 3 — Hybrid RRF, vLLM Briefings & Operational Frontend
- [ ] Sprint 4 — GB10 Observability, Chaos Testing & Benchmarks

### Sprint 1 scope delivered

- Argon2id passwords, EdDSA JWT access tokens, rotating refresh tokens with
  reuse detection (full session-family revocation), WebAuthn passkey
  registration/auth (Redis-backed challenge store), TOTP + recovery codes,
  step-up MFA, 5-tier RBAC, AES-256-GCM + HMAC blind indexing, append-only
  OAIS/PREMIS provenance ledger, append-only audit log.
- Admin slice: users/roles, feature flags, audit log search, audited PII
  unmask gateway.
- CPU-only Document AI (PyMuPDF/python-docx/lxml parsing) and the Atomic JSON
  Write Cache adapter.
- React pages: Login, Register, MFA challenge, Dashboard (placeholder),
  Account & Security (TOTP enrollment, recovery codes, active sessions).
- 17 automated backend tests (unit + adapter + e2e) plus a full manual
  Playwright click-through of register → login → TOTP enroll → MFA-gated
  login → recovery-code login against a live dev stack.

## Getting started (dev)

```bash
cp .env.example .env   # fill in generated secrets, see comments inline
make up                # docker compose --profile core up
make migrate           # alembic upgrade head
```

See `Makefile` for all dev shortcuts.
