# Sprint 2: BGE-M3 embeddings, BGE-reranker-v2-m3, GLiNER NER/PII, MADLAD-400 MT.
FROM nvcr.io/nvidia/pytorch:26.10-py3

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# HF_HUB_CACHE (not HF_HOME -- that expects a "hub/" subfolder nested under
# it) must point directly at the mounted HF-layout cache
# (SV_MODEL_ROOT/.hf_cache) so transformers can resolve backbone assets
# GLiNER checkpoints reference by HF repo ID (e.g. microsoft/mdeberta-v3-base's
# tokenizer) without needing the full model re-downloaded under our own
# SV_MODEL_ROOT tree.
ENV HF_HUB_OFFLINE=1
ENV HF_HUB_CACHE=/data/models/.hf_cache
EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
