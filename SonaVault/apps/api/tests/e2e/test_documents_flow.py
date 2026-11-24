import io

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient

from sonavault.main import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def contributor_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "docs-tester@sanctuary.org"
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


SANCTSOUND_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<SanctSoundSPL station="OC02">
  <Reading timestamp="2024-01-01T00:00:00Z" broadbandDb="98.4">
    <Band name="63Hz">88.1</Band>
  </Reading>
</SanctSoundSPL>
"""


async def test_get_pdf_chunks_end_to_end(contributor_client: AsyncClient):
    pdf_bytes = _make_pdf_bytes("Vessel-routing notice: speed restriction near OC02")
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/document",
        files={"file": ("notice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "pdf"},
    )
    sha256 = ingest_resp.json()["sha256"]

    chunks_resp = await contributor_client.get(f"/api/v1/documents/{sha256}/chunks")
    assert chunks_resp.status_code == 200
    body = chunks_resp.json()
    assert "OC02" in body["chunks"][0]["text"]


async def test_chunks_are_cached_after_first_read(contributor_client: AsyncClient):
    pdf_bytes = _make_pdf_bytes("Field inspection log entry for cache test")
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/document",
        files={"file": ("cache-test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "pdf"},
    )
    sha256 = ingest_resp.json()["sha256"]

    first = await contributor_client.get(f"/api/v1/documents/{sha256}/chunks")
    second = await contributor_client.get(f"/api/v1/documents/{sha256}/chunks")
    assert first.json() == second.json()

    from sonavault.adapters.storage.json_cache import read_projection

    cached = read_projection(asset_sha256=sha256, view="chunks")
    assert cached is not None


async def test_get_telemetry_xml_end_to_end(contributor_client: AsyncClient):
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/document",
        files={"file": ("spl.xml", io.BytesIO(SANCTSOUND_XML), "application/xml")},
        data={"doc_type": "xml"},
    )
    sha256 = ingest_resp.json()["sha256"]

    telemetry_resp = await contributor_client.get(f"/api/v1/documents/{sha256}/telemetry-xml")
    assert telemetry_resp.status_code == 200
    body = telemetry_resp.json()
    assert body["readings"][0]["station_code"] == "OC02"
    assert body["readings"][0]["broadband_db"] == 98.4


async def test_wrong_endpoint_for_asset_type_rejected(contributor_client: AsyncClient):
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/document",
        files={
            "file": ("spl2.xml", io.BytesIO(SANCTSOUND_XML + b"<!--marker-->"), "application/xml")
        },
        data={"doc_type": "xml"},
    )
    sha256 = ingest_resp.json()["sha256"]

    resp = await contributor_client.get(f"/api/v1/documents/{sha256}/chunks")
    assert resp.status_code == 400
