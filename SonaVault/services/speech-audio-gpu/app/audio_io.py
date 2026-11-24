"""Shared audio decode/resample helpers.

soundfile.read() (not torchaudio.load) is used to decode compressed/container
formats, per the architecture note that torchaudio's backend can break on
this image; resampling itself uses torchaudio.functional.resample once we
already have a raw float tensor.
"""

import base64
import io

import numpy as np
import soundfile as sf
import torch
import torchaudio


def decode_audio_b64(audio_b64: str) -> tuple[torch.Tensor, int]:
    """Returns (mono_waveform[1, n_samples], sample_rate)."""
    raw_bytes = base64.b64decode(audio_b64)
    data, sample_rate = sf.read(io.BytesIO(raw_bytes), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)  # collapse to mono if multi-channel
    waveform = torch.from_numpy(mono.astype(np.float32)).unsqueeze(0)
    return waveform, sample_rate


def resample(waveform: torch.Tensor, orig_sr: int, target_sr: int) -> torch.Tensor:
    if orig_sr == target_sr:
        return waveform
    return torchaudio.functional.resample(waveform, orig_sr, target_sr)
