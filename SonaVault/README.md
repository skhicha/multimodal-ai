# SonaVault

**Sovereign Multimodal Acoustic Intelligence Platform for NVIDIA DGX Spark (GB10 Grace-Blackwell)**

[![Tests](https://img.shields.io/badge/tests-121%20passed-emerald)](apps/api/tests/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](apps/api/)
[![Frontend](https://img.shields.io/badge/frontend-React%2018%20%7C%20Vite%20%7C%20TS-cyan)](apps/web/)
[![Hardware](https://img.shields.io/badge/hardware-NVIDIA%20GB10%20(sm__121)-76b900)](infra/)
[![Models](https://img.shields.io/badge/models-100%25%20Open%20Weights-purple)](services/)

SonaVault is a sovereign, open-weight platform for **Multilingual Acoustic Soundscape, Field-Dispatch, and Regulatory Dossier Intelligence** — engineered specifically for coastal marine sanctuary monitoring, maritime incident coordination, and archival bioacoustic research.

The platform is strictly non-visual: zero camera frames, zero raster images. All processed data consists of passive hydrophone audio streams, multilingual spoken radio dispatches, and structured regulatory environmental documentation (PDF, DOCX, NOAA SanctSound XML).

---

## Architecture Overview

```
                                    ┌────────────────────────────────────────────────────────┐
                                    │      React 18 + Vite + Tailwind + Framer Motion SPA    │
                                    │  Dashboard • Streams • Vault • Workbench • Search •    │
                                    │  Briefings • Document AI • Provenance Jobs • Admin     │
                                    └───────────────────────────┬────────────────────────────┘
                                                                │  REST / SSE / LL-HLS
                                                                ▼
┌──────────────────────────────┐    ┌────────────────────────────────────────────────────────┐
│  MediaMTX Streaming Sidecar  │◄───┤              FastAPI Monolith (:8080)                  │
│  LL-HLS 48kHz AAC-LC Streams │    │  Auth • MFA • RBAC • Ingest • Provenance • Briefings   │
└──────────────────────────────┘    └──────────────┬───────────────────┬─────────────────────┘
                                                   │                   │
                     ┌─────────────────────────────┴─────┐      ┌──────┴─────────────────────┐
                     │          Worker & Storage         │      │     Postgres 16 + Redis    │
                     │  • RQ Distributed Job Workers     │      │  • Encrypted Asset Records │
                     │  • NVMe CAS Blob Storage          │      │  • OAIS/PREMIS Ledger      │
                     │  • Atomic JSON Write Cache        │      │  • WebAuthn / Token Store  │
                     └───────────────────────────────────┘      └────────────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                    NVIDIA GB10 Blackwell & Grace Sidecar Microservices                     │
│                                                                                            │
│  ┌─────────────────────────┐   ┌───────────────────────────┐   ┌────────────────────────┐  │
│  │ speech-audio-gpu (:8001)│   │  nlp-retrieval-gpu (:8002)│   │  vllm-moe-gpu (:8000)  │  │
│  │ • Whisper v3 Turbo ASR  │   │  • BGE-M3 Dense + Sparse  │   │  • Qwen3-30B-A3B-NVFP4 │  │
│  │ • pyannote Diarization  │   │  • BGE-Reranker v2 M3     │   │  • FP8 KV Cache Engine │  │
│  │ • AST Acoustic Tagging  │   │  • GLiNER Domain/PII NER  │   │  • Chunked Prefill     │  │
│  │ • CLAP 512d Embeddings  │   │  • MADLAD-400 419-Lang MT │   │  • SSE Token Streaming │  │
│  └─────────────────────────┘   └───────────────────────────┘   └────────────────────────┘  │
│                                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Qdrant v1.20 Vector Database (Hybrid Reciprocal Rank Fusion, k=60)                  │  │
│  │  Collections: transcript_segments (1024d) • acoustic_events (512d) • doc_chunks      │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Host Memory Watchdog Daemon & Hardware Observability                                │  │
│  │  • Unified LPDDR5X (128GB) Memory Monitoring over NVLink-C2C                         │  │
│  │  • 4-Level Backpressure Throttling (Normal, Warning, Backpressure, Emergency)        │  │
│  │  • Prometheus Metrics Exporter & Provisioned Grafana Dashboards                      │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4-Sprint Implementation Matrix

All four planned architectural sprints have been fully implemented, rigorously tested, and verified:

| Sprint | Scope & Key Components | Status |
|---|---|:---:|
| **Sprint 0** | Monorepo scaffold, Docker Compose topology, strict pre-commit hooks, ruff linting, SQLite/Postgres dual-engine configuration. | **Delivered** |
| **Sprint 1** | Argon2id hashing, Ed25519 JWT auth, WebAuthn Passkeys, TOTP, 5-tier RBAC, AES-256-GCM envelope encryption, HMAC blind indexing, OAIS/PREMIS provenance ledger. | **Delivered** |
| **Sprint 2** | GPU sidecars (`speech-audio-gpu`, `nlp-retrieval-gpu`), MediaMTX LL-HLS audio streaming, 7-stage resumable ingestion DAG with checkpoint admission control. | **Delivered** |
| **Sprint 3** | Qdrant hybrid RRF search (`k=60`), vLLM `Qwen3-30B-A3B-NVFP4` streaming briefings with citation verification, and full 9-feature React SPA frontend. | **Delivered** |
| **Sprint 4** | GB10 unified LPDDR5X memory telemetry, Host Memory Watchdog daemon, chaos engineering test suite, and DeepEval quantitative RAG evaluation suite. | **Delivered** |

---

## Key Platform Capabilities

### 1. Resumable 7-Stage Ingestion DAG
Audio and document assets pass through a deterministic, checkpoint-controlled ingestion pipeline:
1. **Stage 1 (Preprocess)**: Magic bytes verification, RIFF/WAV format validation, or PyMuPDF / python-docx / NOAA XML telemetry extraction.
2. **Stage 2 (Speech)**: Whisper v3 Turbo multilingual transcription coupled with pyannote speaker diarization turn-overlap matching.
3. **Stage 3 (Acoustic)**: AST spectrogram event classification (AudioSet taxonomy) + CLAP 512-dimensional audio embeddings.
4. **Stage 4 (NLP)**: GLiNER zero-shot domain entity recognition & automated PII redaction (person names, coordinates, callsigns).
5. **Stage 5 (Index)**: Multi-collection upsert into Qdrant (`transcript_segments`, `acoustic_events`, `document_chunks`) using deterministic point UUIDs to guarantee idempotency.
6. **Stage 6 (Seal)**: Atomic JSON projection cache emission + cryptographically chained OAIS/PREMIS event sealing with SHA-256 verification.

### 2. Hybrid Reciprocal Rank Fusion (RRF) Retrieval
- Combines dense semantic vector search (BGE-M3 1024d) and sparse lexical BM25-equivalent indices via Reciprocal Rank Fusion (`RRF score = Σ [1 / (60 + rank)]`).
- Re-ranks candidates through `bge-reranker-v2-m3` cross-encoder for high-precision citation retrieval.
- Enforces strict sanctuary-scoping and 5-tier RBAC (`public_guest`, `field_contributor`, `sanctuary_ranger`, `marine_analyst`, `archivist`).

### 3. Sovereign Briefing Synthesis with Cited Grounding
- Powered by `nvidia/Qwen3-30B-A3B-NVFP4` served on Blackwell sm_121 architecture via vLLM with FP8 KV caching and chunked prefill.
- Strict `<evidence>` prompt framing forces the LLM to synthesize operational dossiers exclusively from retrieved context.
- Streaming client state-machine strips `<think>...</think>` internal reasoning blocks on the fly.
- Real-time regex citation validation checks all cited references `[SHA-256 @ mm:ss]` against authorized evidence before generating cryptographic PREMIS export dossiers.

### 4. GB10 Unified Memory Watchdog & Observability
- Monitors Grace ARM64 + Blackwell GPU unified LPDDR5X memory (128GB) connected via NVLink-C2C high-bandwidth bus.
- **Host Memory Watchdog**:
  - `normal` (<80%): Full-speed streaming and ingestion.
  - `warning` (80%–90%): Proactive alerts.
  - `backpressure` (90%–95%): Activates backpressure gauge, pausing non-critical ingest jobs.
  - `emergency` (≥95%): Automatically executes garbage collection, cache relief, and connection shedding.
- **Grafana & Prometheus**: Pre-provisioned dashboards in `infra/grafana/` tracking LPDDR5X allocation, GPU compute utilization, die temperatures, vLLM MoE request queues, and sidecar p95 latencies.

### 5. Automated Chaos & Resilience Engineering
- Network chaos test suite validating sidecar connection drops, HTTP 502/503 service failures, and transient self-recovery.
- Audio degradation test suite asserting graceful handling of zeroed buffers (pure silence), clipped signals, DC offsets, and malformed WAV headers.
- Pipeline idempotency chaos verifying mid-stage crash recovery via `/api/v1/jobs/{id}/resume` with zero duplicate points in Qdrant and preserved PREMIS chain validity.

### 6. DeepEval Quantitative RAG Evaluation Suite
- Quantitative test cases evaluated using DeepEval:
  - **Citation Precision**: Asserts 100% of generated citations match verified evidence hashes without fabrication.
  - **Evidence Faithfulness**: Measures factual grounding against retrieved `<evidence>` tags.
  - **Answer Relevancy**: Asserts query intent coverage and structured executive reporting.
  - **Adversarial Resistance**: Validates that prompt injection attempts (e.g. system prompt or KEK key extraction) are neutralized.

---

## Web Frontend Features (`apps/web`)

The frontend is a single-page application built with React 18, Vite, TypeScript, Tailwind CSS, Framer Motion, and Recharts:

1. **Sanctuary Acoustic Telemetry Map**: Interactive SVG marine array tracking hydrophone stations (CI01, FK01, OC02, SB01, MB01) with live 24h sound pressure level (SPL) charts and live GB10 Watchdog telemetry.
2. **Low-Latency Audio Streams**: Live hydrophone audio listening via MediaMTX LL-HLS with real-time waveform visualizers and instant clip extraction.
3. **Sovereign Vault & Ingest**: Multi-format file ingestion (WAV, FLAC, PDF, DOCX, XML) with drag-and-drop, SHA-256 verification, and metadata attribution.
4. **Interactive Audio Workbench**: Waveform scrubbing, synchronized speaker-diarized transcripts, hitl transcript editing, and MADLAD-400 machine translation.
5. **Hybrid Search Studio**: Multi-modal search interface allowing dense semantic, sparse lexical, and hybrid cross-encoder queries across spoken transcripts, acoustic events, and documents.
6. **Sovereign Intelligence Briefings**: Real-time SSE streaming briefing generator citing raw evidence with PDF/JSON dossier export.
7. **Document Intelligence Viewer**: PDF/DOCX chunk reader with bounding-box metadata and sanctuary scoping.
8. **Provenance & Jobs DAG**: Visual 7-stage DAG execution tracker showing step status, execution latency, and PREMIS cryptographic hash chains.
9. **Security & Admin Console**: 5-tier user role management, account locking, feature flag toggles, and audited PII unmasking.

---

## Directory Layout

```
SonaVault/
├── apps/
│   ├── api/                     # FastAPI monolith application
│   │   ├── src/sonavault/       # Vertical slices (auth, ingest, search, briefings, telemetry, etc.)
│   │   │   ├── adapters/        # Sidecars, Qdrant, NVMe blob storage, JSON cache
│   │   │   ├── core/            # Pipeline orchestrator, security, RBAC, provenance ledger
│   │   │   ├── models/          # SQLAlchemy async ORM models
│   │   │   ├── services/        # Watchdog daemon, queue workers
│   │   │   └── slices/          # Feature slices with typed schemas and routers
│   │   └── tests/               # 121 automated tests (adapters, unit, e2e, chaos, eval, security)
│   └── web/                     # React 18 + Vite + TypeScript frontend SPA
│       ├── src/components/      # AppShell, navigation, modals
│       ├── src/features/        # 9 feature views (dashboard, streams, vault, audio, briefings, etc.)
│       └── src/lib/             # Typed API client, WebAuthn helpers
├── data/
│   ├── blobs/                   # Content-addressed raw audio & document payloads
│   └── models/                  # Open-source weights (Whisper, pyannote, AST, CLAP, BGE, Qwen3)
├── docs/                        # Complete technical architecture blueprint
├── infra/
│   ├── docker/                  # Docker Compose, MediaMTX, and Prometheus configuration
│   ├── grafana/                 # Pre-provisioned Grafana datasources and dashboards
│   └── observability/           # Production GB10 Grafana dashboard JSON
└── services/
    ├── nlp-retrieval-gpu/       # BGE-M3, BGE-Reranker, GLiNER, MADLAD-400 sidecar
    └── speech-audio-gpu/        # Whisper v3 Turbo, pyannote diarization, AST, CLAP sidecar
```

---

## Development Setup

### Prerequisites
- Linux OS (Ubuntu 22.04+ or DGX OS recommended)
- Python 3.12+ (or uv package manager)
- Node.js 20+ & npm
- Docker & Docker Compose with NVIDIA Container Toolkit

### 1. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your generated cryptographic master keys and service tokens
```

### 2. Infrastructure Services (Docker)
```bash
# Start core database and vector storage
docker compose -f infra/docker/docker-compose.yml --profile core up -d

# Start GPU sidecar services (requires NVIDIA GPU)
docker compose -f infra/docker/docker-compose.yml --profile vllm up -d
```

### 3. Backend Setup & Database Migrations
```bash
cd apps/api
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
alembic upgrade head
python -m uvicorn sonavault.main:app --host 0.0.0.0 --port 8080 --reload
```

### 4. Frontend Setup
```bash
cd apps/web
npm install
npm run dev
# Vite server starts at http://localhost:5173
```

### 5. Running the Complete Verification Suite
```bash
# Run all 121 tests (Unit, E2E, Adapters, Chaos, DeepEval)
PYTHONPATH=apps/api:apps/api/src apps/api/.venv/bin/pytest apps/api/tests/ -v

# Run code style & formatting checks
apps/api/.venv/bin/ruff check apps/api
apps/api/.venv/bin/ruff format --check apps/api

# Build frontend production bundle
cd apps/web && npm run build
```

---

## License

Licensed under the Apache License, Version 2.0. Model weights are subject to their respective open-source licenses (MIT, Apache 2.0, OpenRAIL).
