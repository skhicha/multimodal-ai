"""One-time offline HF model mirror into /data/models.

Run this BEFORE setting HF_HUB_OFFLINE=1. Downloads all 9 permissively
licensed models used by SonaVault's speech-audio-gpu and nlp-retrieval-gpu
sidecars (plus the vLLM MoE checkpoint). Requires HF_TOKEN in the
environment with the pyannote/speaker-diarization-community-1 license
accepted on huggingface.co first.

Usage:
    HF_TOKEN=hf_... python scripts/download_models.py [--only NAME ...]
"""

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ROOT = Path(os.environ.get("SV_MODEL_ROOT", "./data/models"))

MODELS: dict[str, dict] = {
    "whisper": {"repo_id": "openai/whisper-large-v3-turbo"},
    "diarization": {"repo_id": "pyannote/speaker-diarization-community-1"},
    "segmentation": {"repo_id": "pyannote/segmentation-3.0"},
    "ast": {"repo_id": "MIT/ast-finetuned-audioset-10-10-0.4593"},
    "clap": {"repo_id": "laion/clap-htsat-fused"},
    "bge-m3": {"repo_id": "BAAI/bge-m3"},
    "bge-reranker": {"repo_id": "BAAI/bge-reranker-v2-m3"},
    "gliner": {"repo_id": "urchade/gliner_multi-v2.1"},
    "madlad400": {"repo_id": "google/madlad400-3b-mt"},
    "vllm-moe": {"repo_id": "nvidia/Qwen3-30B-A3B-NVFP4"},
    # gliner_multi-v2.1's checkpoint has no bundled tokenizer: its
    # gliner_config.json names this backbone by HF repo ID and GLiNER
    # resolves the tokenizer via plain `AutoTokenizer.from_pretrained(repo_id)`
    # at load time. With HF_HUB_OFFLINE=1 that only works if the repo is
    # already sitting in the *standard* HF hub cache layout (not a flat
    # `local_dir`), so this one is downloaded into SV_MODEL_ROOT/.hf_cache
    # instead, with HF_HOME pointed there in the sidecar Dockerfile.
    "gliner-backbone-tokenizer": {
        "repo_id": "microsoft/mdeberta-v3-base",
        "cache_mode": True,
        "allow_patterns": ["tokenizer*", "spm.model", "*.json", "vocab*"],
    },
}


def download_one(
    key: str, repo_id: str, *, token: str | None, cache_mode: bool = False, allow_patterns=None
) -> None:
    if cache_mode:
        cache_dir = MODEL_ROOT / ".hf_cache"
        print(f"[{key}] downloading {repo_id} -> {cache_dir} (HF cache layout)", flush=True)
        snapshot_download(
            repo_id=repo_id,
            cache_dir=cache_dir,
            token=token,
            max_workers=4,
            allow_patterns=allow_patterns,
        )
    else:
        local_dir = MODEL_ROOT / repo_id
        print(f"[{key}] downloading {repo_id} -> {local_dir}", flush=True)
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            token=token,
            max_workers=4,
        )
    print(f"[{key}] done", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None, help="Subset of model keys to download")
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("WARNING: HF_TOKEN not set; gated models (pyannote) will fail.", file=sys.stderr)

    keys = args.only or list(MODELS.keys())
    unknown = set(keys) - set(MODELS.keys())
    if unknown:
        print(f"Unknown model keys: {unknown}. Valid: {list(MODELS.keys())}", file=sys.stderr)
        sys.exit(1)

    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    for key in keys:
        spec = MODELS[key]
        download_one(
            key,
            spec["repo_id"],
            token=token,
            cache_mode=spec.get("cache_mode", False),
            allow_patterns=spec.get("allow_patterns"),
        )

    print("All requested models downloaded.")


if __name__ == "__main__":
    main()
