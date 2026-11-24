"""End-to-end ingest regression test: real magic-byte validation, real
content-addressed blob storage on disk, real SHA-256 dedup, and real geo-QA
flagging — run against the live FastAPI app."""

import io

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient

from sonavault.main import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def auth_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "ingest-tester@sanctuary.org"
        await c.post(
            "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
        )
        login = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login['access_token']}"

        from sqlalchemy import select

        from sonavault.db import SessionLocal
        from sonavault.models.auth import User

        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            user.role = "field_contributor"
            await session.commit()

        login2 = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login2['access_token']}"
        yield c


def _make_pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_wav_bytes() -> bytes:
    import struct

    sample_rate = 16000
    num_samples = sample_rate // 10  # 100ms of silence
    data = struct.pack(f"<{num_samples}h", *([0] * num_samples))
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
    )
    return header + data


async def test_ingest_audio_real_wav_file(auth_client: AsyncClient):
    wav_bytes = _make_wav_bytes() + b"marker:test_ingest_audio_real_wav_file"
    resp = await auth_client.post(
        "/api/v1/ingest/audio",
        files={"file": ("hydrophone.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={
            "sanctuary_id": "OC02",
            "station_code": "OC02",
            "latitude": "47.9",
            "longitude": "-124.8",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["asset_type"] == "audio"
    assert body["deduplicated"] is False
    assert body["geo_qa_flag"] is None
    assert len(body["sha256"]) == 64


async def test_ingest_same_audio_twice_deduplicates(auth_client: AsyncClient):
    wav_bytes = _make_wav_bytes() + b"marker:test_ingest_same_audio_twice_deduplicates"
    r1 = await auth_client.post(
        "/api/v1/ingest/audio", files={"file": ("a.wav", io.BytesIO(wav_bytes), "audio/wav")}
    )
    r2 = await auth_client.post(
        "/api/v1/ingest/audio", files={"file": ("a-copy.wav", io.BytesIO(wav_bytes), "audio/wav")}
    )
    assert r1.json()["sha256"] == r2.json()["sha256"]
    assert r1.json()["deduplicated"] is False
    assert r2.json()["deduplicated"] is True


async def test_ingest_flags_geo_qa_station_mismatch(auth_client: AsyncClient):
    wav_bytes = _make_wav_bytes()
    resp = await auth_client.post(
        "/api/v1/ingest/audio",
        files={"file": ("bad-coords.wav", io.BytesIO(wav_bytes + b"x"), "audio/wav")},
        # ~1 degree longitude off from the registered OC02 station.
        data={"station_code": "OC02", "latitude": "47.9", "longitude": "-123.8"},
    )
    assert resp.status_code == 201
    assert resp.json()["geo_qa_flag"] == "STATION_MISMATCH"


async def test_ingest_rejects_renamed_file_wrong_magic_bytes(auth_client: AsyncClient):
    """A text file renamed to look like a .wav must be rejected — magic
    bytes are checked, not the client-supplied extension/content-type."""
    fake_wav = b"this is definitely not a WAV file, just plain text"
    resp = await auth_client.post(
        "/api/v1/ingest/audio", files={"file": ("fake.wav", io.BytesIO(fake_wav), "audio/wav")}
    )
    assert resp.status_code == 422


async def test_ingest_real_pdf_document(auth_client: AsyncClient):
    pdf_bytes = _make_pdf_bytes("Vessel-routing notice for sanctuary OC02")
    resp = await auth_client.post(
        "/api/v1/ingest/document",
        files={"file": ("notice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "pdf"},
    )
    assert resp.status_code == 201
    assert resp.json()["asset_type"] == "pdf"


async def test_ingest_requires_field_contributor_tier():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "viewer-only@sanctuary.org"
        await c.post(
            "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
        )
        login = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login['access_token']}"

        resp = await c.post(
            "/api/v1/ingest/audio",
            files={"file": ("x.wav", io.BytesIO(_make_wav_bytes()), "audio/wav")},
        )
        assert resp.status_code == 403


async def test_list_and_get_asset(auth_client: AsyncClient):
    wav_bytes = _make_wav_bytes() + b"unique-marker"
    create_resp = await auth_client.post(
        "/api/v1/ingest/audio",
        files={"file": ("list-test.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    sha256 = create_resp.json()["sha256"]

    get_resp = await auth_client.get(f"/api/v1/ingest/assets/{sha256}")
    assert get_resp.status_code == 200
    assert get_resp.json()["sha256"] == sha256

    list_resp = await auth_client.get("/api/v1/ingest/assets?asset_type=audio")
    assert list_resp.status_code == 200
    assert any(a["sha256"] == sha256 for a in list_resp.json())
