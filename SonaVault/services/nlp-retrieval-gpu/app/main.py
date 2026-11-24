"""nlp-retrieval-gpu sidecar: BGE-M3 dense+sparse embeddings,
BGE-reranker-v2-m3 cross-encoder, GLiNER zero-shot NER/PII, MADLAD-400-3B-MT
translation. Real model inference — no stubs.

torch.cuda.set_per_process_memory_fraction(0.18, device=0) gives this sidecar
an ~21.5 GiB ceiling, enough for BGE-M3 + BGE-reranker + GLiNER + MADLAD-400
BF16 comfortably per the GB10 unified-memory budget.
"""

import logging

from fastapi import FastAPI, Header, HTTPException

from app import config
from app.models import (
    BgeM3Embedding,
    EmbedRequest,
    EmbedResponse,
    NerEntity,
    NerRequest,
    NerResponse,
    RerankRequest,
    RerankResponse,
    RerankResult,
    SparseVector,
    TranslateRequest,
    TranslateResponse,
)

logger = logging.getLogger("nlp-retrieval-gpu")
app = FastAPI(title="nlp-retrieval-gpu")

_state: dict = {}


def _check_token(x_internal_service_token: str | None) -> None:
    if config.INTERNAL_SERVICE_TOKEN and x_internal_service_token != config.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(401, "Invalid or missing internal service token")


@app.on_event("startup")
async def load_models() -> None:
    import torch

    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(config.MEMORY_FRACTION, device=0)
        logger.info("CUDA available: %s", torch.cuda.get_device_name(0))
    else:
        logger.warning("CUDA not available; running on CPU (dev/test mode)")

    from FlagEmbedding import BGEM3FlagModel, FlagReranker

    logger.info("Loading BGE-M3 from %s", config.BGE_M3_PATH)
    _state["bge_m3"] = BGEM3FlagModel(str(config.BGE_M3_PATH), use_fp16=torch.cuda.is_available())

    logger.info("Loading BGE-reranker-v2-m3 from %s", config.BGE_RERANKER_PATH)
    _state["reranker"] = FlagReranker(
        str(config.BGE_RERANKER_PATH), use_fp16=torch.cuda.is_available()
    )

    logger.info("Loading GLiNER from %s", config.GLINER_PATH)
    from gliner import GLiNER

    gliner_model = GLiNER.from_pretrained(str(config.GLINER_PATH), local_files_only=True)
    if torch.cuda.is_available():
        gliner_model = gliner_model.to("cuda")
    _state["gliner"] = gliner_model

    logger.info("Loading MADLAD-400-3B-MT from %s", config.MADLAD400_PATH)
    from transformers import AutoTokenizer, T5ForConditionalGeneration

    _state["mt_tokenizer"] = AutoTokenizer.from_pretrained(str(config.MADLAD400_PATH))
    mt_model = T5ForConditionalGeneration.from_pretrained(
        str(config.MADLAD400_PATH), torch_dtype=torch.bfloat16
    )
    if torch.cuda.is_available():
        mt_model = mt_model.to("cuda")
    _state["mt_model"] = mt_model

    logger.info("All nlp-retrieval-gpu models loaded")


@app.get("/healthz")
async def healthz():
    ready = all(k in _state for k in ("bge_m3", "reranker", "gliner", "mt_model"))
    return {"status": "ok" if ready else "loading", "service": "nlp-retrieval-gpu"}


@app.post("/v1/embed/bge-m3", response_model=EmbedResponse)
async def embed_bge_m3(body: EmbedRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    model = _state["bge_m3"]
    output = model.encode(
        body.texts, return_dense=True, return_sparse=True, return_colbert_vecs=False
    )

    embeddings = []
    for dense_vec, lexical_weights in zip(
        output["dense_vecs"], output["lexical_weights"], strict=True
    ):
        indices = [int(k) for k in lexical_weights]
        values = [float(v) for v in lexical_weights.values()]
        embeddings.append(
            BgeM3Embedding(
                dense=dense_vec.tolist(), sparse=SparseVector(indices=indices, values=values)
            )
        )
    return EmbedResponse(embeddings=embeddings)


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    reranker = _state["reranker"]
    pairs = [[body.query, doc] for doc in body.documents]
    scores = reranker.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]
    results = [RerankResult(index=i, score=float(s)) for i, s in enumerate(scores)]
    return RerankResponse(results=results)


@app.post("/v1/ner/gliner", response_model=NerResponse)
async def ner_gliner(body: NerRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    model = _state["gliner"]
    raw_entities = model.predict_entities(body.text, body.labels, threshold=0.5)
    entities = [
        NerEntity(
            text=e["text"],
            label=e["label"],
            start=e["start"],
            end=e["end"],
            score=float(e["score"]),
        )
        for e in raw_entities
    ]
    return NerResponse(entities=entities)


@app.post("/v1/translate", response_model=TranslateResponse)
async def translate(body: TranslateRequest, x_internal_service_token: str | None = Header(None)):
    _check_token(x_internal_service_token)
    import torch

    tokenizer = _state["mt_tokenizer"]
    model = _state["mt_model"]

    prefixed_text = f"<2{body.target_lang}> {body.text}"
    inputs = tokenizer(prefixed_text, return_tensors="pt", truncation=True, max_length=512)
    if torch.cuda.is_available():
        inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=512)
    translated = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    return TranslateResponse(translated_text=translated, detected_source_lang=None)
