"""
Visual scene captioning using BLIP (CPU), distinct from speech
transcription (asr.py). Describes what a photo, or a video's keyframes,
actually SHOW -- "a man in a yellow turban standing next to a white wall"
-- not what anyone said. This is what lets Search/Ask AI answer questions
about silent or speech-free footage, and photos, which asr.py can never
help with at all.

First run downloads the model weights from Hugging Face (~990MB) -- needs
internet access once; cached locally afterward. If the download fails (no
internet, blocked network, disk issue) or the model otherwise can't load,
captioning is skipped and the rest of the processing pipeline continues
normally -- exactly the same fail-safe contract asr.py already uses, so a
media item never fails to upload because this optional step couldn't run.
"""
from __future__ import annotations

import threading
from typing import Optional

_model_lock = threading.Lock()
_model = None
_processor = None
_model_load_failed = False

MODEL_NAME = "Salesforce/blip-image-captioning-base"


def _get_model():
    global _model, _processor, _model_load_failed
    if _model is not None:
        return _model, _processor
    if _model_load_failed:
        return None, None
    with _model_lock:
        if _model is not None or _model_load_failed:
            return _model, _processor
        try:
            from transformers import BlipForConditionalGeneration, BlipProcessor

            _processor = BlipProcessor.from_pretrained(MODEL_NAME)
            _model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME)
        except Exception as exc:  # noqa: BLE001 - must never crash the pipeline
            print(f"[captioning] BLIP model unavailable, skipping captioning step: {exc}")
            _model_load_failed = True
            _model = None
            _processor = None
    return _model, _processor


def caption_image(bgr_image) -> Optional[str]:
    """Takes an OpenCV BGR image (the same ndarray vision.py already works
    with, so no extra image I/O is needed), returns a short English scene
    description, or None if the model is unavailable or captioning this
    frame fails for any reason."""
    model, processor = _get_model()
    if model is None or processor is None:
        return None
    try:
        import cv2
        from PIL import Image

        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
        inputs = processor(pil_image, return_tensors="pt")
        # Plain greedy decoding on this model reliably produces repeated
        # phrases on real-world photos (observed: "a yellow turban and a
        # yellow turban", "a beard and a beard") -- beam search with a
        # repetition penalty and an n-gram block is the standard, verified
        # fix (confirmed clean across 8 real test photos before shipping).
        out = model.generate(**inputs, max_new_tokens=30, num_beams=4, repetition_penalty=1.5, no_repeat_ngram_size=3)
        caption = processor.decode(out[0], skip_special_tokens=True).strip()
        return caption or None
    except Exception as exc:  # noqa: BLE001
        print(f"[captioning] caption generation failed: {exc}")
        return None
