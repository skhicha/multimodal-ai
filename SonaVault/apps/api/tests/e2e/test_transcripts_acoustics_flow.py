import uuid

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from sonavault.adapters.storage import blob_nvme
from sonavault.config import get_settings
from sonavault.db import SessionLocal
from sonavault.main import create_app
from sonavault.models.acoustics import AcousticEvent, TranscriptSegment
from sonavault.models.assets import Asset
from sonavault.models.auth import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def analyst_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "analyst-tester@sanctuary.org"
        await c.post(
            "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
        )
        login = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login['access_token']}"

        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            user.role = "acoustic_analyst"
            await session.commit()

        login2 = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login2['access_token']}"
        yield c


async def _seed_asset_with_segment_and_event() -> tuple[str, str, str]:
    sha256 = blob_nvme.put(uuid.uuid4().bytes + b"transcript-acoustics-test")
    async with SessionLocal() as session:
        session.add(Asset(sha256=sha256, asset_type="audio", mime_type="audio/wav", size_bytes=32))
        seg = TranscriptSegment(
            asset_sha256=sha256,
            seg_index=0,
            start_sec=0.0,
            end_sec=2.0,
            text_redacted="humpback whale call observed",
            model_version="v1",
        )
        event = AcousticEvent(
            asset_sha256=sha256,
            window_start_sec=0.0,
            window_end_sec=10.24,
            audioset_label="Whale vocalization",
            confidence=0.9,
            spl_db_broadband=98.4,
        )
        session.add(seg)
        session.add(event)
        await session.commit()
        return sha256, str(seg.id), str(event.id)


async def test_get_transcript_returns_segments(analyst_client: AsyncClient):
    sha256, _, _ = await _seed_asset_with_segment_and_event()
    resp = await analyst_client.get(f"/api/v1/transcripts/{sha256}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["segments"]) == 1
    assert "humpback whale" in body["segments"][0]["text_redacted"]


async def test_edit_segment_sets_hitl_override(analyst_client: AsyncClient):
    sha256, seg_id, _ = await _seed_asset_with_segment_and_event()
    resp = await analyst_client.patch(
        f"/api/v1/transcripts/{sha256}/segments/{seg_id}",
        json={"text_redacted": "corrected transcript text"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text_redacted"] == "corrected transcript text"
    assert body["is_hitl_override"] is True


async def test_edit_nonexistent_segment_404s(analyst_client: AsyncClient):
    sha256, _, _ = await _seed_asset_with_segment_and_event()
    resp = await analyst_client.patch(
        f"/api/v1/transcripts/{sha256}/segments/{uuid.uuid4()}",
        json={"text_redacted": "x"},
    )
    assert resp.status_code == 404


async def test_edit_segment_requires_analyst_tier():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "low-tier@sanctuary.org"
        await c.post(
            "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
        )
        login = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login['access_token']}"

        sha256, seg_id, _ = await _seed_asset_with_segment_and_event()
        resp = await c.patch(
            f"/api/v1/transcripts/{sha256}/segments/{seg_id}", json={"text_redacted": "nope"}
        )
        assert resp.status_code == 403


@respx.mock
async def test_translate_transcript_calls_sidecar_and_caches_result(analyst_client: AsyncClient):
    settings = get_settings()
    route = respx.post(f"{settings.nlp_sidecar_url}/v1/translate").mock(
        return_value=Response(
            200,
            json={
                "translated_text": "llamada de ballena jorobada observada",
                "detected_source_lang": "en",
            },
        )
    )
    sha256, _, _ = await _seed_asset_with_segment_and_event()

    resp = await analyst_client.post(
        f"/api/v1/transcripts/{sha256}/translate", json={"target_lang": "es"}
    )
    assert resp.status_code == 200
    assert (
        resp.json()["segments"][0]["translations_json"]["es"]
        == "llamada de ballena jorobada observada"
    )
    assert route.call_count == 1

    # Re-translating to the same language must not call the sidecar again.
    resp2 = await analyst_client.post(
        f"/api/v1/transcripts/{sha256}/translate", json={"target_lang": "es"}
    )
    assert resp2.status_code == 200
    assert route.call_count == 1


async def test_get_events_and_spl_timeline(analyst_client: AsyncClient):
    sha256, _, _ = await _seed_asset_with_segment_and_event()

    events_resp = await analyst_client.get(f"/api/v1/acoustics/{sha256}/events")
    assert events_resp.status_code == 200
    assert events_resp.json()["events"][0]["audioset_label"] == "Whale vocalization"

    spl_resp = await analyst_client.get(f"/api/v1/acoustics/{sha256}/spl")
    assert spl_resp.status_code == 200
    assert spl_resp.json() == [98.4]


async def test_edit_event_sets_hitl_override(analyst_client: AsyncClient):
    sha256, _, event_id = await _seed_asset_with_segment_and_event()
    resp = await analyst_client.patch(
        f"/api/v1/acoustics/{sha256}/events/{event_id}", json={"audioset_label": "Boat engine"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["audioset_label"] == "Boat engine"
    assert body["is_hitl_override"] is True
