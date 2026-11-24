import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


MODEL_ROOT = Path(_env("SV_MODEL_ROOT", "/data/models"))
INTERNAL_SERVICE_TOKEN = _env("SV_INTERNAL_SERVICE_TOKEN", "")
MEMORY_FRACTION = float(_env("PYTORCH_CUDA_MEM_FRACTION", "0.15"))

WHISPER_PATH = MODEL_ROOT / "openai" / "whisper-large-v3-turbo"
DIARIZATION_PATH = MODEL_ROOT / "pyannote" / "speaker-diarization-community-1"
AST_PATH = MODEL_ROOT / "MIT" / "ast-finetuned-audioset-10-10-0.4593"
CLAP_PATH = MODEL_ROOT / "laion" / "clap-htsat-fused"

AST_WINDOW_SECONDS = 10.24
