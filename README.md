# Multimodal AI & Sensory Intelligence Systems

A collection of sovereign, production-grade Multimodal AI platforms spanning acoustic intelligence, bioacoustic monitoring, vision-language media understanding, cross-modal retrieval, and cited generative reasoning.

Designed and engineered for real-world hardware deployments — from edge laptops to NVIDIA DGX Blackwell platforms.

---

## 🏛️ Projects in this Portfolio

<table>
<tr>
<td width="50%" valign="top">

### 🌊 [SonaVault: Acoustic Intelligence Platform](./SonaVault)
**Sovereign Bioacoustic & Spoken Audio Intelligence on NVIDIA DGX Spark GB10**

A 100%-open-source, non-visual multimodal platform processing hydrophone soundscapes, multilingual field dispatches, and regulatory environmental documentation. Fully delivered across all 4 architectural sprints with 121 automated tests.

- **Audio & Speech Perception**: `openai/whisper-large-v3-turbo` ASR, `pyannote/speaker-diarization-community-1`, `MIT/ast-finetuned-audioset` acoustic tagging, `laion/clap-htsat-fused` cross-modal audio-text embeddings.
- **Text & Document AI**: `BAAI/bge-m3` dense/sparse embeddings, `BAAI/bge-reranker-v2-m3` cross-encoder, `urchade/gliner_multi-v2.1` zero-shot PII/domain NER, `google/madlad400-3b-mt` 419-language MT.
- **Pipeline & Infrastructure**: 7-stage resumable ingestion DAG with checkpoint admission control, MediaMTX Low-Latency HLS (LL-HLS) audio streaming, Qdrant v1.20 3-collection hybrid RRF search (`k=60`), OAIS/PREMIS hash-chained provenance ledger with cryptographic immutability, WebAuthn/FIDO2 passkeys + Argon2id MFA security.
- **Hardware & Observability**: Built atop NVIDIA Blackwell GB10 unified memory (128 GB), sm_121 architecture, running `nvidia/Qwen3-30B-A3B-NVFP4` via vLLM with FP8 KV cache. Features a 4-level Host Memory Watchdog daemon, provisioned Grafana dashboards, chaos test suite, and DeepEval quantitative RAG evaluation.
- **Frontend SPA**: Full 9-feature React 18 + Vite + TypeScript application with Tailwind CSS, Framer Motion, and Recharts.

`PyTorch` `CUDA 13` `vLLM` `Qdrant RRF` `FastAPI` `React 18` `Tailwind` `MediaMTX` `DeepEval`

</td>
<td width="50%" valign="top">

### 📸 [MemoryLens AI: Personal Media Vault](./memorylens-ai-vault)

**Local Multimodal Personal Media & Vision-Language Intelligence**

A fully local AI media intelligence vault auto-processing photos and videos with computer vision, audio transcription, spatio-temporal clustering, and cited RAG conversation.

- **Vision & Scene Understanding**: OpenCV facial detection and embeddings, BLIP visual scene captioning, EXIF GPS spatio-temporal clustering.
- **Speech Perception**: Faster-Whisper audio transcription and keyword extraction.
- **Search & Retrieval**: SQLite FTS5 full-text search across visual captions and spoken transcripts, paired with vector embeddings for semantic query matching.
- **Generative Assistant**: Offline extractive QA assistant and local LLM chat answering questions with clickable citations back to exact photo timestamps and video frames.
- **Security & Privacy**: Role-based access control (admin / editor / viewer), revocable sessions, cross-device logout, and authenticator-app 2FA.

`Python` `OpenCV` `Whisper` `BLIP` `FastAPI` `React 18` `TypeScript` `SQLite FTS5`

</td>
</tr>
</table>

---

## 🎯 Conceptual Scope: What is Multimodal AI?

Multimodal AI unifies perception across distinct sensory modalities — sound, speech, vision, structured telemetry, and natural language — enabling machines to reason across heterogenous data streams:

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 Sensory Ingestion                      │
                  │  Hydrophones (WAV/FLAC) │ Video/Photos │ Documents/XML │
                  └─────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼
                  ┌────────────────────────────────────────────────────────┐
                  │           Modality-Specific Encoders                   │
                  │  • Audio: Whisper v3 Turbo, pyannote, AST, CLAP        │
                  │  • Vision: OpenCV, BLIP scene captioning               │
                  │  • NLP: BGE-M3, GLiNER NER, MADLAD-400 MT              │
                  └─────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼
                  ┌────────────────────────────────────────────────────────┐
                  │         Cross-Modal Vector & Hybrid Indexing           │
                  │  • Qdrant Universal Query / RRF (Reciprocal Rank)      │
                  │  • Dense + Sparse Lexical Fusion + Cross-Encoder       │
                  └─────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼
                  ┌────────────────────────────────────────────────────────┐
                  │      Verifiable Synthesis & RAG with Strict Citations  │
                  │  • Qwen3-30B NVFP4 MoE / Local LLM Streaming           │
                  │  • Verifiable citations [SHA-256 @ mm:ss]               │
                  └────────────────────────────────────────────────────────┘
```

### Key Engineering Themes
1. **Zero-Hallucination Grounding**: Every AI assertion is backed by cryptographically verifiable citations to raw audio timestamps or visual frames.
2. **Hardware-Aware Execution**: Tailored optimizations ranging from resource-constrained laptop edge runtimes to 128 GB unified-memory NVIDIA Blackwell GB10 SoCs.
3. **Open-Weight Autonomy**: 100% permissively licensed open models running entirely on-premise without external cloud API dependencies.
4. **Append-Only Provenance**: OAIS/PREMIS-inspired hash-chained ledgers and audit trails ensuring regulatory data integrity.

---

## 📂 Repository Navigation

```
multimodal-ai/
├── SonaVault/              # Sovereign Acoustic Intelligence Platform (DGX Spark GB10)
├── memorylens-ai-vault/    # Personal Media & Vision-Language Intelligence Vault
└── README.md               # Portfolio index & multimodal architecture guide
```

---

<p align="center">
Built by <a href="https://github.com/skhicha"><b>Shubham Khicha</b></a>
</p>
