import pytest
from httpx import ASGITransport, AsyncClient

from sonavault.main import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login_as(
    client: AsyncClient, *, email: str, role: str, sanctuary_scopes: list[str]
) -> str:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
    )

    if role != "viewer" or sanctuary_scopes:
        from sqlalchemy import select

        from sonavault.db import SessionLocal
        from sonavault.models.auth import User

        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            user.role = role
            user.sanctuary_scopes = sanctuary_scopes
            await session.commit()

    login = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    return login["access_token"]


async def test_mint_token_requires_sanctuary_scope(client: AsyncClient):
    token = await _login_as(
        client, email="scoped-viewer@sanctuary.org", role="viewer", sanctuary_scopes=["OC02"]
    )
    resp = await client.post(
        "/api/v1/streams/OC02/token", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


async def test_mint_token_denied_for_out_of_scope_station(client: AsyncClient):
    token = await _login_as(
        client, email="other-scope-viewer@sanctuary.org", role="viewer", sanctuary_scopes=["OC02"]
    )
    resp = await client.post(
        "/api/v1/streams/RESTRICTED_ZONE/token", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_archivist_can_mint_token_for_any_station(client: AsyncClient):
    token = await _login_as(
        client, email="archivist1@sanctuary.org", role="archivist", sanctuary_scopes=[]
    )
    resp = await client.post(
        "/api/v1/streams/ANY_STATION/token", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


async def test_mediamtx_auth_accepts_valid_token_for_matching_station(client: AsyncClient):
    token = await _login_as(
        client, email="stream-viewer@sanctuary.org", role="viewer", sanctuary_scopes=["OC02"]
    )
    mint_resp = await client.post(
        "/api/v1/streams/OC02/token", headers={"Authorization": f"Bearer {token}"}
    )
    stream_token = mint_resp.json()["token"]

    auth_resp = await client.post(
        "/api/v1/streams/mediamtx-auth",
        json={"path": "hydrophone/OC02", "action": "read", "password": stream_token},
    )
    assert auth_resp.status_code == 200


async def test_mediamtx_auth_rejects_token_for_different_station(client: AsyncClient):
    token = await _login_as(
        client, email="cross-station@sanctuary.org", role="archivist", sanctuary_scopes=[]
    )
    mint_resp = await client.post(
        "/api/v1/streams/OC02/token", headers={"Authorization": f"Bearer {token}"}
    )
    stream_token = mint_resp.json()["token"]

    # Same token, but MediaMTX reports a connection to a different station path.
    auth_resp = await client.post(
        "/api/v1/streams/mediamtx-auth",
        json={"path": "hydrophone/RESTRICTED_ZONE", "action": "read", "password": stream_token},
    )
    assert auth_resp.status_code == 401


async def test_mediamtx_auth_rejects_missing_token(client: AsyncClient):
    resp = await client.post(
        "/api/v1/streams/mediamtx-auth", json={"path": "hydrophone/OC02", "action": "read"}
    )
    assert resp.status_code == 401


async def test_mediamtx_auth_rejects_garbage_token(client: AsyncClient):
    resp = await client.post(
        "/api/v1/streams/mediamtx-auth",
        json={"path": "hydrophone/OC02", "action": "read", "password": "not-a-real-jwt"},
    )
    assert resp.status_code == 401


async def test_mediamtx_auth_rejects_non_stream_scoped_token(client: AsyncClient):
    """An access token (wrong scope) must not be usable as a stream token."""
    token = await _login_as(
        client, email="scope-confusion@sanctuary.org", role="archivist", sanctuary_scopes=[]
    )
    auth_resp = await client.post(
        "/api/v1/streams/mediamtx-auth",
        json={"path": "hydrophone/OC02", "action": "read", "password": token},
    )
    assert auth_resp.status_code == 401


async def test_list_streams_returns_stations_for_archivist(client: AsyncClient):
    token = await _login_as(
        client, email="stream-lister@sanctuary.org", role="archivist", sanctuary_scopes=[]
    )
    resp = await client.get("/api/v1/streams", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    codes = {s["station_code"] for s in body}
    assert "OC02" in codes
    assert "MB01" in codes


async def test_create_stream_and_capture_clip(client: AsyncClient):
    token = await _login_as(
        client,
        email="analyst-capture@sanctuary.org",
        role="acoustic_analyst",
        sanctuary_scopes=["OC02", "TEST_STATION"],
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/v1/streams",
        headers=headers,
        json={
            "station_code": "TEST_STATION",
            "name": "Test Hydrophone Station",
            "sanctuary_id": "TEST_STATION",
            "latitude": 48.0,
            "longitude": -125.0,
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["station_code"] == "TEST_STATION"

    # Capture rolling clip
    capture_resp = await client.post(
        "/api/v1/streams/TEST_STATION/capture",
        headers=headers,
        json={"duration_sec": 10.0, "notes": "Whale click sequence captured live"},
    )
    assert capture_resp.status_code == 200
    cbody = capture_resp.json()
    assert cbody["sha256"]
    assert cbody["job_id"]
    assert cbody["station_code"] == "TEST_STATION"
