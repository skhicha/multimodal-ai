# Sprint 2: Whisper ASR, pyannote diarization, AST events, CLAP embeddings.
# Native sm_121 CUDA 13 base — torch/torchvision/torchaudio stripped from
# requirements.txt below so pip install never overwrites NVIDIA's Blackwell
# PyTorch build.
FROM nvcr.io/nvidia/pytorch:26.10-py3

WORKDIR /app
COPY requirements.txt .
# --ignore-installed: pyannote.audio pulls in pytorch-lightning, which wants a
# newer PyYAML than the one baked into this NGC image via apt/debian (no pip
# RECORD file, so pip can't uninstall it to upgrade in place). Installing the
# newer PyYAML alongside rather than trying to replace the system one avoids
# the "uninstall-no-record-file" build failure.
#
# Note: pyannote.audio's resolver pulls its own torch==2.15.0 (matching its
# torchaudio pin) over the NGC base image's torch==2.15.0a0+875d815502.nv26.10
# build; pip's resolver refuses an exact pin to the NGC local-version string
# since no matching distribution exists on PyPI to satisfy backtracking, so we
# cannot constrain it back. Verified at container runtime that the resulting
# PyPI torch 2.15.0 (CUDA 13 wheel) still loads and runs on this sm_121 GPU.
RUN pip install --no-cache-dir --ignore-installed PyYAML -r requirements.txt

COPY app/ ./app/

ENV HF_HUB_OFFLINE=1
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
