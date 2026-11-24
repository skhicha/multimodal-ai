import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


MODEL_ROOT = Path(_env("SV_MODEL_ROOT", "/data/models"))
INTERNAL_SERVICE_TOKEN = _env("SV_INTERNAL_SERVICE_TOKEN", "")
MEMORY_FRACTION = float(_env("PYTORCH_CUDA_MEM_FRACTION", "0.18"))

BGE_M3_PATH = MODEL_ROOT / "BAAI" / "bge-m3"
BGE_RERANKER_PATH = MODEL_ROOT / "BAAI" / "bge-reranker-v2-m3"
GLINER_PATH = MODEL_ROOT / "urchade" / "gliner_multi-v2.1"
MADLAD400_PATH = MODEL_ROOT / "google" / "madlad400-3b-mt"
