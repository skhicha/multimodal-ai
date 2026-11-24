import io

import pytest
from httpx import ASGITransport, AsyncClient

from sonavault.main import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def contributor_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "jobs-tester@sanctuary.org"
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


def _make_wav_bytes(marker: bytes) -> bytes:
    import struct

    sample_rate = 16000
    num_samples = sample_rate // 10
    data = struct.pack(f"<{num_samples}h", *([0] * num_samples)) + marker
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
    )
    return header + data


async def test_ingest_creates_pipeline_job_with_all_stages_pending(contributor_client: AsyncClient):
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/audio",
        files={"file": ("job-test.wav", io.BytesIO(_make_wav_bytes(b"jobs-test-1")), "audio/wav")},
    )
    job_id = ingest_resp.json()["job_id"]
    assert job_id

    job_resp = await contributor_client.get(f"/api/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    body = job_resp.json()
    assert body["status"] == "pending"
    assert len(body["stages"]) == 6
    assert all(s["status"] == "pending" for s in body["stages"])


async def test_list_jobs_filters_by_asset(contributor_client: AsyncClient):
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/audio",
        files={"file": ("job-test2.wav", io.BytesIO(_make_wav_bytes(b"jobs-test-2")), "audio/wav")},
    )
    sha256 = ingest_resp.json()["sha256"]

    list_resp = await contributor_client.get(f"/api/v1/jobs?asset_sha256={sha256}")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert len(jobs) == 1
    assert jobs[0]["asset_sha256"] == sha256


async def test_resume_job_sets_status_pending_and_current_stage(contributor_client: AsyncClient):
    ingest_resp = await contributor_client.post(
        "/api/v1/ingest/audio",
        files={"file": ("job-test3.wav", io.BytesIO(_make_wav_bytes(b"jobs-test-3")), "audio/wav")},
    )
    job_id = ingest_resp.json()["job_id"]

    resume_resp = await contributor_client.post(f"/api/v1/jobs/{job_id}/resume")
    assert resume_resp.status_code == 200
    body = resume_resp.json()
    assert body["current_stage"] == "preprocess"  # first stage, nothing succeeded yet


async def test_get_nonexistent_job_returns_404(contributor_client: AsyncClient):
    import uuid

    resp = await contributor_client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_jobs_require_field_contributor_tier():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = "jobs-viewer-only@sanctuary.org"
        await c.post(
            "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
        )
        login = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login['access_token']}"

        resp = await c.get("/api/v1/jobs")
        assert resp.status_code == 403
