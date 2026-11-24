import httpx
import pytest
import respx
from httpx import Response

from sonavault.adapters.sidecars import nlp_client, speech_client
from sonavault.config import get_settings

pytestmark = pytest.mark.asyncio


@respx.mock
async def test_transcribe_parses_response():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(
            200,
            json={
                "segments": [
                    {
                        "start_sec": 0.0,
                        "end_sec": 2.5,
                        "text": "humpback call detected",
                        "language": "en",
                    }
                ],
                "detected_language": "en",
            },
        )
    )
    result = await speech_client.transcribe(b"fake-audio-bytes")
    assert result.detected_language == "en"
    assert result.segments[0].text == "humpback call detected"


@respx.mock
async def test_diarize_parses_turns():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/diarize").mock(
        return_value=Response(
            200, json={"turns": [{"start_sec": 0.0, "end_sec": 3.2, "speaker_label": "SPEAKER_00"}]}
        )
    )
    result = await speech_client.diarize(b"fake-audio-bytes")
    assert result.turns[0].speaker_label == "SPEAKER_00"


@respx.mock
async def test_ast_events_parses_sigmoid_labels():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(
            200,
            json={
                "events": [
                    {
                        "window_start_sec": 0.0,
                        "window_end_sec": 10.24,
                        "labels": {"Whale vocalization": 0.91, "Engine noise": 0.12},
                    }
                ]
            },
        )
    )
    result = await speech_client.ast_events(b"fake-audio-bytes")
    assert result.events[0].labels["Whale vocalization"] == 0.91


@respx.mock
async def test_clap_audio_embedding_is_512d():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/embed/clap-audio").mock(
        return_value=Response(200, json={"embedding": [0.1] * 512})
    )
    result = await speech_client.embed_clap_audio(b"fake-audio-bytes")
    assert len(result.embedding) == 512


@respx.mock
async def test_bge_m3_embed_returns_dense_and_sparse():
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/embed/bge-m3").mock(
        return_value=Response(
            200,
            json={
                "embeddings": [
                    {"dense": [0.01] * 1024, "sparse": {"indices": [3, 7], "values": [0.5, 0.2]}}
                ]
            },
        )
    )
    results = await nlp_client.embed_bge_m3(["humpback whale vocalization near OC02"])
    assert len(results[0].dense) == 1024
    assert results[0].sparse.indices == [3, 7]


@respx.mock
async def test_rerank_returns_sigmoid_scores():
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/rerank").mock(
        return_value=Response(200, json={"results": [{"index": 0, "score": 0.87}]})
    )
    result = await nlp_client.rerank("whale calls", ["transcript segment text"])
    assert result.results[0].score == 0.87


@respx.mock
async def test_gliner_ner_parses_entities():
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/ner/gliner").mock(
        return_value=Response(
            200,
            json={
                "entities": [
                    {
                        "text": "WDF1234",
                        "label": "vessel_callsign",
                        "start": 10,
                        "end": 17,
                        "score": 0.95,
                    }
                ]
            },
        )
    )
    result = await nlp_client.ner_gliner("Vessel WDF1234 reported", labels=["vessel_callsign"])
    assert result.entities[0].label == "vessel_callsign"


@respx.mock
async def test_translate_returns_detected_lang():
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/translate").mock(
        return_value=Response(200, json={"translated_text": "Hello", "detected_source_lang": "es"})
    )
    result = await nlp_client.translate("Hola", target_lang="en")
    assert result.translated_text == "Hello"
    assert result.detected_source_lang == "es"


@respx.mock
async def test_healthz_returns_false_on_connection_error():
    settings = get_settings()
    respx.get(f"{settings.speech_sidecar_url}/healthz").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await speech_client.healthz() is False
