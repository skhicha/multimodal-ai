"""Typed HTTPX client for the vLLM MoE sidecar (:8000 in Docker, :18000 on host).

Interacts with OpenAI-compatible /v1/chat/completions endpoint for streaming
and batch generation with Qwen3-30B-A3B-NVFP4 on NVIDIA DGX Spark GB10.
"""

import json
import re
from collections.abc import AsyncIterator

import httpx

from sonavault.config import get_settings

TIMEOUT_SECONDS = 180.0


def _get_base_url() -> str:
    settings = get_settings()
    return settings.vllm_base_url


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_get_base_url(),
        timeout=httpx.Timeout(TIMEOUT_SECONDS, read=None),
    )


async def healthz() -> bool:
    try:
        async with _client() as client:
            resp = await client.get("/health")
            if resp.status_code == 200:
                return True
            resp2 = await client.get("/v1/models")
            return resp2.status_code == 200
    except (httpx.HTTPError, Exception):
        return False


def strip_think_tags(text: str) -> str:
    """Strip <think>...</think> blocks from reasoning models."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    strip_thinking: bool = True,
) -> str:
    settings = get_settings()
    target_model = model or settings.vllm_model_id
    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with _client() as client:
        resp = await client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"] or ""
        if strip_thinking:
            content = strip_think_tags(content)
        return content


async def stream_chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    filter_thinking: bool = False,
) -> AsyncIterator[str]:
    """Streams token chunks from vLLM chat completions.

    If filter_thinking is True, strips out reasoning content between <think> and </think>.
    """
    settings = get_settings()
    target_model = model or settings.vllm_model_id
    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    async with _client() as client:
        async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            in_think = False
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: ") :].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if not content:
                        continue

                    if filter_thinking:
                        if "<think>" in content:
                            in_think = True
                            parts = content.split("<think>", 1)
                            if parts[0]:
                                yield parts[0]
                            content = parts[1]
                        if in_think:
                            if "</think>" in content:
                                in_think = False
                                parts = content.split("</think>", 1)
                                content = parts[1].lstrip("\n")
                                if content:
                                    yield content
                            continue

                    yield content
                except json.JSONDecodeError:
                    continue
