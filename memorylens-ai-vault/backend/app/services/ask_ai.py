"""
Ask AI: a small retrieval-augmented-generation flow.

Retrieval: FTS5 search over filenames/tags/transcripts, used to build a
citation list of (media id, filename, source, timestamp, snippet).

Generation is pluggable via LLM_PROVIDER:
  - "mock" (default): no API key, no network call. Builds an extractive,
    clearly-labelled "offline mode" answer purely out of the retrieved
    snippets -- it never invents facts not present in the citations.
  - "anthropic": calls the real Claude API (anthropic Python SDK) with the
    retrieved context, instructed to answer only from it and cite sources.
  - "gemini": calls the Google Gemini API (google-genai Python SDK) with the
    same retrieved context and the same answer-only-from-context, cite-sources
    behavior as the anthropic path.
  - "openai": calls the OpenAI Chat Completions API (openai Python SDK) with
    the same retrieved context and the same answer-only-from-context,
    cite-sources behavior as the anthropic/gemini paths.
  - "ollama": calls a locally-running Ollama server (free, no API key, no
    network egress) over its OpenAI-compatible HTTP endpoint, with the same
    answer-only-from-context, cite-sources behavior as the other paths.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from app.db import db_cursor
from app.services.search import search as fts_search


@dataclass
class Citation:
    media_id: str
    filename: str
    media_type: str
    source: str
    segment_start: float | None
    snippet: str


@dataclass
class AskResult:
    answer: str
    citations: List[Citation]
    provider: str


def _gather_citations(question: str, user_id: str, limit: int = 8) -> List[Citation]:
    hits = fts_search(question, limit=limit, user_id=user_id, mode="or")
    citations: List[Citation] = []
    seen = set()
    for hit in hits:
        key = (hit.media_id, hit.source, hit.segment_start)
        if key in seen:
            continue
        seen.add(key)
        with db_cursor() as cur:
            cur.execute(
                "SELECT filename, media_type FROM media WHERE id = ? AND user_id = ?",
                (hit.media_id, user_id),
            )
            row = cur.fetchone()
        if not row:
            continue
        citations.append(
            Citation(
                media_id=hit.media_id,
                filename=row["filename"],
                media_type=row["media_type"],
                source=hit.source,
                segment_start=hit.segment_start,
                snippet=hit.text,
            )
        )
    return citations


def _mock_answer(question: str, citations: List[Citation]) -> str:
    if not citations:
        return (
            "[Offline mode / mock provider] I couldn't find anything in your vault that "
            "matches that question. Try different words, or upload and process some media first. "
            "This answer is template-based and only ever repeats what full-text search finds -- "
            "it never makes facts up."
        )
    lines = [
        "[Offline mode / mock provider -- no LLM API key used] "
        "Here is what your vault's full-text index actually contains for this question:",
        "",
    ]
    for i, c in enumerate(citations[:5], start=1):
        where = f" at {c.segment_start:.1f}s" if c.segment_start is not None else ""
        lines.append(f"{i}. [{c.filename}]{where} ({c.source}): \"{c.snippet.replace('<mark>', '').replace('</mark>', '')}\"")
    lines.append("")
    lines.append(
        "Switch LLM_PROVIDER=anthropic in backend/.env (with ANTHROPIC_API_KEY set) "
        "for a fluent, synthesized answer over these same citations."
    )
    return "\n".join(lines)


def _anthropic_answer(question: str, citations: List[Citation]) -> str:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _mock_answer(question, citations) + "\n\n(ANTHROPIC_API_KEY not set -- fell back to offline mode.)"

    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    context_blocks = []
    for i, c in enumerate(citations, start=1):
        where = f" at {c.segment_start:.1f}s" if c.segment_start is not None else ""
        clean_snippet = c.snippet.replace("<mark>", "").replace("</mark>", "")
        context_blocks.append(f"[{i}] file={c.filename}{where} source={c.source}\n{clean_snippet}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no matching media found)"

    system = (
        "You are the Ask AI assistant for MemoryLens AI, a personal photo/video vault. "
        "Answer the user's question using ONLY the numbered context snippets below, which come "
        "from the user's own transcripts/tags/filenames. Cite sources inline like [1], [2]. "
        "If the context doesn't contain the answer, say so plainly -- never invent details, "
        "dates, or people that are not present in the context."
    )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    text_parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_parts).strip() or _mock_answer(question, citations)


GEMINI_TIMEOUT_SECONDS = 300


def _gemini_answer(question: str, citations: List[Citation]) -> str:
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _mock_answer(question, citations) + "\n\n(GEMINI_API_KEY not set -- fell back to offline mode.)"

    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    context_blocks = []
    for i, c in enumerate(citations, start=1):
        where = f" at {c.segment_start:.1f}s" if c.segment_start is not None else ""
        clean_snippet = c.snippet.replace("<mark>", "").replace("</mark>", "")
        context_blocks.append(f"[{i}] file={c.filename}{where} source={c.source}\n{clean_snippet}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no matching media found)"

    system = (
        "You are the Ask AI assistant for MemoryLens AI, a personal photo/video vault. "
        "Answer the user's question using ONLY the numbered context snippets below, which come "
        "from the user's own transcripts/tags/filenames. Cite sources inline like [1], [2]. "
        "If the context doesn't contain the answer, say so plainly -- never invent details, "
        "dates, or people that are not present in the context."
    )
    client = genai.Client(api_key=api_key)

    def _call():
        return client.models.generate_content(
            model=model,
            contents=f"Context:\n{context}\n\nQuestion: {question}",
            config={"system_instruction": system, "max_output_tokens": 600},
        )

    # The SDK retries internally on transient errors (e.g. 503s) for several
    # minutes with no way to configure that away, which makes a slow/overloaded
    # Gemini backend look like a hung chat UI. Bound it with our own timeout so
    # a slow call falls back to the instant mock answer instead of stalling.
    # NOTE: a plain `with ThreadPoolExecutor()` blocks on __exit__ until the
    # worker finishes, which would silently undo the timeout -- so this calls
    # shutdown(wait=False) explicitly instead of using the context manager.
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_call)
    try:
        response = future.result(timeout=GEMINI_TIMEOUT_SECONDS)
    except FutureTimeoutError:
        pool.shutdown(wait=False)
        raise TimeoutError(
            f"Gemini did not respond within {GEMINI_TIMEOUT_SECONDS}s"
        ) from None
    else:
        pool.shutdown(wait=False)

    text = (getattr(response, "text", None) or "").strip()
    return text or _mock_answer(question, citations)


OPENAI_TIMEOUT_SECONDS = 60


def _openai_answer(question: str, citations: List[Citation]) -> str:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _mock_answer(question, citations) + "\n\n(OPENAI_API_KEY not set -- fell back to offline mode.)"

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    context_blocks = []
    for i, c in enumerate(citations, start=1):
        where = f" at {c.segment_start:.1f}s" if c.segment_start is not None else ""
        clean_snippet = c.snippet.replace("<mark>", "").replace("</mark>", "")
        context_blocks.append(f"[{i}] file={c.filename}{where} source={c.source}\n{clean_snippet}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no matching media found)"

    system = (
        "You are the Ask AI assistant for MemoryLens AI, a personal photo/video vault. "
        "Answer the user's question using ONLY the numbered context snippets below, which come "
        "from the user's own transcripts/tags/filenames. Cite sources inline like [1], [2]. "
        "If the context doesn't contain the answer, say so plainly -- never invent details, "
        "dates, or people that are not present in the context."
    )
    client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)
    response = client.chat.completions.create(
        model=model,
        max_tokens=600,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    return text or _mock_answer(question, citations)


OLLAMA_TIMEOUT_SECONDS = 120


def _ollama_answer(question: str, citations: List[Citation]) -> str:
    import httpx

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    context_blocks = []
    for i, c in enumerate(citations, start=1):
        where = f" at {c.segment_start:.1f}s" if c.segment_start is not None else ""
        clean_snippet = c.snippet.replace("<mark>", "").replace("</mark>", "")
        context_blocks.append(f"[{i}] file={c.filename}{where} source={c.source}\n{clean_snippet}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no matching media found)"

    system = (
        "You are the Ask AI assistant for MemoryLens AI, a personal photo/video vault. "
        "Answer the user's question using ONLY the numbered context snippets below, which come "
        "from the user's own transcripts/tags/filenames. Cite sources inline like [1], [2]. "
        "If the context doesn't contain the answer, say so plainly -- never invent details, "
        "dates, or people that are not present in the context."
    )
    response = httpx.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
            ],
            "options": {"num_predict": 600},
        },
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    text = (data.get("message", {}).get("content") or "").strip()
    return text or _mock_answer(question, citations)


def answer_question(question: str, user_id: str) -> AskResult:
    citations = _gather_citations(question, user_id)
    provider = os.environ.get("LLM_PROVIDER", "mock").lower()

    if provider == "anthropic":
        try:
            answer = _anthropic_answer(question, citations)
        except Exception as exc:  # noqa: BLE001 - never 500 the chat on provider errors
            answer = (
                f"[Anthropic provider error, falling back to offline mode: {exc}]\n\n"
                + _mock_answer(question, citations)
            )
            provider = "mock (fallback)"
    elif provider == "gemini":
        try:
            answer = _gemini_answer(question, citations)
        except Exception as exc:  # noqa: BLE001 - never 500 the chat on provider errors
            answer = (
                f"[Gemini provider error, falling back to offline mode: {exc}]\n\n"
                + _mock_answer(question, citations)
            )
            provider = "mock (fallback)"
    elif provider == "openai":
        try:
            answer = _openai_answer(question, citations)
        except Exception as exc:  # noqa: BLE001 - never 500 the chat on provider errors
            answer = (
                f"[OpenAI provider error, falling back to offline mode: {exc}]\n\n"
                + _mock_answer(question, citations)
            )
            provider = "mock (fallback)"
    elif provider == "ollama":
        try:
            answer = _ollama_answer(question, citations)
        except Exception as exc:  # noqa: BLE001 - never 500 the chat on provider errors
            answer = (
                f"[Ollama provider error, falling back to offline mode: {exc}]\n\n"
                + _mock_answer(question, citations)
            )
            provider = "mock (fallback)"
    else:
        answer = _mock_answer(question, citations)
        provider = "mock"

    return AskResult(answer=answer, citations=citations, provider=provider)
