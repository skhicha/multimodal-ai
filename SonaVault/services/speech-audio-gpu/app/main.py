"""speech-audio-gpu sidecar: Whisper ASR, pyannote diarization, AST event
tagging, CLAP audio/text embeddings. Real model inference — no stubs.

torch.cuda.set_per_process_memory_fraction(0.15, device=0) gives this sidecar
an ~18 GiB ceiling on the GB10's unified-memory pool since cudaMalloc is
invisible to Linux cgroups.
"""

import logging

import torch
import torch.nn.functional as F
from fastapi import FastAPI, Header, HTTPException

from app import config
from app.audio_io import decode_audio_b64, resample
from app.models import (
    AcousticEventOut,
    AstEventsResponse,
    AudioRequest,
    ClapEmbeddingResponse,
    ClapTextRequest,
    DiarizationTurnOut,
    DiarizeResponse,
    TranscribeResponse,
    TranscriptSegmentOut,
)

logger = logging.getLogger("speech-audio-gpu")
app = FastAPI(title="speech-audio-gpu")

_state: dict = {}
_device = "cuda" if torch.cuda.is_available() else "cpu"


def _check_token(x_internal_service_token: str | None) -> None:
    if config.INTERNAL_SERVICE_TOKEN and x_internal_service_token != config.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(401, "Invalid or missing internal service token")


@app.on_event("startup")
async def load_models() -> None:
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(config.MEMORY_FRACTION, device=0)
        logger.info("CUDA available: %s", torch.cuda.get_device_name(0))
    else:
        logger.warning("CUDA not available; running on CPU (dev/test mode)")

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    logger.info("Loading Whisper ASR pipeline from %s", config.WHISPER_PATH)
    from transformers import pipeline as hf_pipeline

    _state["asr"] = hf_pipeline(
        "automatic-speech-recognition",
        model=str(config.WHISPER_PATH),
        torch_dtype=dtype,
        device=_device,
        chunk_length_s=30,
        return_timestamps=True,
    )

    logger.info("Loading pyannote diarization pipeline from %s", config.DIARIZATION_PATH)
    from pyannote.audio import Pipeline as PyannotePipeline

    diarization_pipeline = PyannotePipeline.from_pretrained(str(config.DIARIZATION_PATH))
    if torch.cuda.is_available():
        diarization_pipeline.to(torch.device("cuda"))
    _state["diarization"] = diarization_pipeline

    logger.info("Loading AST from %s", config.AST_PATH)
    from transformers import ASTFeatureExtractor, ASTForAudioClassification

    _state["ast_extractor"] = ASTFeatureExtractor.from_pretrained(str(config.AST_PATH))
    ast_model = ASTForAudioClassification.from_pretrained(str(config.AST_PATH)).to(_device)
    ast_model.eval()
    _state["ast_model"] = ast_model

    logger.info("Loading CLAP from %s", config.CLAP_PATH)
    from transformers import ClapModel, ClapProcessor

    _state["clap_processor"] = ClapProcessor.from_pretrained(str(config.CLAP_PATH))
    clap_model = ClapModel.from_pretrained(str(config.CLAP_PATH)).to(_device)
    clap_model.eval()
    _state["clap_model"] = clap_model

    logger.info("All speech-audio-gpu models loaded")


@app.get("/healthz")
async def healthz():
    ready = all(k in _state for k in ("asr", "diarization", "ast_model", "clap_model"))
    return {"status": "ok" if ready else "loading", "service": "speech-audio-gpu"}


@app.post("/v1/transcribe", response_model=TranscribeResponse)
async def transcribe(body: AudioRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    waveform, sr = decode_audio_b64(body.audio_b64)
    waveform = resample(waveform, sr, 16000)

    asr = _state["asr"]
    generate_kwargs = {"language": body.language_hint} if body.language_hint else {}
    result = asr(waveform.squeeze(0).numpy(), generate_kwargs=generate_kwargs)

    chunks = result.get("chunks") or [{"timestamp": (0.0, None), "text": result.get("text", "")}]
    segments = [
        TranscriptSegmentOut(
            start_sec=float(c["timestamp"][0] or 0.0),
            end_sec=float(c["timestamp"][1])
            if c["timestamp"][1] is not None
            else float(c["timestamp"][0] or 0.0),
            text=c["text"].strip(),
            language=body.language_hint,
        )
        for c in chunks
        if c["text"].strip()
    ]
    detected_language = body.language_hint or "en"
    return TranscribeResponse(segments=segments, detected_language=detected_language)


@app.post("/v1/diarize", response_model=DiarizeResponse)
async def diarize(body: AudioRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    waveform, sr = decode_audio_b64(body.audio_b64)

    pipeline = _state["diarization"]
    diarization = pipeline({"waveform": waveform, "sample_rate": sr})

    turns = [
        DiarizationTurnOut(start_sec=turn.start, end_sec=turn.end, speaker_label=speaker)
        for turn, _, speaker in diarization.speaker_diarization.itertracks(yield_label=True)
    ]
    return DiarizeResponse(turns=turns)


@app.post("/v1/events/ast", response_model=AstEventsResponse)
async def ast_events(body: AudioRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    waveform, sr = decode_audio_b64(body.audio_b64)
    waveform = resample(waveform, sr, 16000)
    samples = waveform.squeeze(0).numpy()

    window_samples = int(config.AST_WINDOW_SECONDS * 16000)
    extractor = _state["ast_extractor"]
    model = _state["ast_model"]
    id2label = model.config.id2label

    events = []
    for start in range(0, max(len(samples), 1), window_samples):
        window = samples[start : start + window_samples]
        if len(window) == 0:
            continue
        inputs = extractor(window, sampling_rate=16000, return_tensors="pt").to(_device)
        with torch.no_grad():
            logits = model(**inputs).logits
        probs = torch.sigmoid(logits)[0]
        top = torch.topk(probs, k=min(10, probs.shape[-1]))
        labels = {id2label[int(i)]: float(p) for p, i in zip(top.values, top.indices, strict=True)}

        window_start_sec = start / 16000
        window_end_sec = min(start + window_samples, len(samples)) / 16000
        events.append(
            AcousticEventOut(
                window_start_sec=window_start_sec, window_end_sec=window_end_sec, labels=labels
            )
        )
    return AstEventsResponse(events=events)


@app.post("/v1/embed/clap-audio", response_model=ClapEmbeddingResponse)
async def embed_clap_audio(body: AudioRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    waveform, sr = decode_audio_b64(body.audio_b64)
    waveform = resample(waveform, sr, 48000)

    processor = _state["clap_processor"]
    model = _state["clap_model"]
    inputs = processor(
        audio=waveform.squeeze(0).numpy(), sampling_rate=48000, return_tensors="pt"
    ).to(_device)
    with torch.no_grad():
        features = model.get_audio_features(**inputs).pooler_output
    normalized = F.normalize(features, p=2, dim=-1)[0]
    return ClapEmbeddingResponse(embedding=normalized.tolist())


@app.post("/v1/embed/clap-text", response_model=ClapEmbeddingResponse)
async def embed_clap_text(
    body: ClapTextRequest, x_internal_service_token: str | None = Header(None)
):
    _check_token(x_internal_service_token)
    processor = _state["clap_processor"]
    model = _state["clap_model"]
    inputs = processor(text=[body.text], return_tensors="pt", padding=True).to(_device)
    with torch.no_grad():
        features = model.get_text_features(**inputs).pooler_output
    normalized = F.normalize(features, p=2, dim=-1)[0]
    return ClapEmbeddingResponse(embedding=normalized.tolist())
