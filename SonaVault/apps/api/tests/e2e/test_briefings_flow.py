import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from sonavault.db import SessionLocal
from sonavault.main import create_app
from sonavault.models.auth import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def auth_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"briefing-analyst-{uuid.uuid4().hex[:8]}@sanctuary.org"
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
            user.sanctuary_scopes = ["TESTSANC-01"]
            user.tier = 2  # analyst
            await session.commit()

        yield c, user.id


async def test_briefings_synthesize_stream_end_to_end(auth_client):
    client, user_id = auth_client
    resp = await client.post(
        "/api/v1/briefings/synthesize",
        json={
            "prompt": "Evaluate acoustic telemetry and biophony indicators for sanctuary.",
            "sanctuary_scope": "TESTSANC-01",
            "max_evidence_chunks": 4,
        },
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = []
    lines = resp.text.split("\n")
    current_event = None
    for line in lines:
        if line.startswith("event: "):
            current_event = line[len("event: ") :].strip()
        elif line.startswith("data: ") and current_event:
            data = json.loads(line[len("data: ") :].strip())
            events.append((current_event, data))
            current_event = None

    event_types = [e[0] for e in events]
    assert "evidence" in event_types
    assert "chunk" in event_types
    assert "done" in event_types

    done_event = next(e[1] for e in events if e[0] == "done")
    assert "briefing_id" in done_event
    briefing_id = done_event["briefing_id"]
    assert isinstance(done_event["cited_sha256s"], list)

    # Verify listing
    list_resp = await client.get("/api/v1/briefings")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == briefing_id for item in items)

    # Verify get by id
    get_resp = await client.get(f"/api/v1/briefings/{briefing_id}")
    assert get_resp.status_code == 200
    briefing_data = get_resp.json()
    assert briefing_data["id"] == briefing_id
    assert briefing_data["user_id"] == str(user_id)
    assert len(briefing_data["markdown_body"]) > 0

    # Verify export dossier
    export_resp = await client.get(f"/api/v1/briefings/{briefing_id}/export")
    assert export_resp.status_code == 200
    dossier_data = export_resp.json()
    assert dossier_data["briefing_id"] == briefing_id
    assert "SONAVAULT SOVEREIGN ACOUSTIC INTELLIGENCE DOSSIER" in dossier_data["dossier_markdown"]
    assert "INTEGRITY DIGEST (SHA-256)" in dossier_data["dossier_markdown"]
    assert "PREMIS CRYPTOGRAPHIC SEAL" in dossier_data["dossier_markdown"]


async def test_briefings_unauthorized_isolation(auth_client):
    client1, _ = auth_client

    # Synthesize briefing with client 1
    resp = await client1.post(
        "/api/v1/briefings/synthesize",
        json={
            "prompt": "Classified maritime vessel surveillance assessment.",
            "max_evidence_chunks": 2,
        },
    )
    assert resp.status_code == 200
    lines = resp.text.split("\n")
    briefing_id = None
    for line in lines:
        if line.startswith("data: ") and "briefing_id" in line:
            briefing_id = json.loads(line[len("data: ") :].strip())["briefing_id"]
            break
    assert briefing_id is not None

    # Register second user
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client2:
        email2 = f"outsider-{uuid.uuid4().hex[:8]}@other.org"
        await client2.post(
            "/api/v1/auth/register", json={"email": email2, "password": "CorrectHorseBattery9"}
        )
        login2 = (
            await client2.post(
                "/api/v1/auth/login", json={"email": email2, "password": "CorrectHorseBattery9"}
            )
        ).json()
        client2.headers["Authorization"] = f"Bearer {login2['access_token']}"

        # Client2 attempts to access client1's briefing -> must be 403 Forbidden
        denied_resp = await client2.get(f"/api/v1/briefings/{briefing_id}")
        assert denied_resp.status_code == 403
