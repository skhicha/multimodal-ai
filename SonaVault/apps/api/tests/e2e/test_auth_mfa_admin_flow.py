"""End-to-end regression test for the full Sprint 1 auth/MFA/admin flow,
run against the real FastAPI app with an isolated SQLite DB and fake Redis
(see conftest.py). Exercises exactly the scenarios manually verified during
development: register -> login -> TOTP enroll/confirm -> MFA-gated login ->
TOTP replay rejection -> recovery-code single-use -> refresh rotation ->
refresh reuse detection (full session-family revocation) -> RBAC 401 vs 403
-> step-up MFA gate on sensitive admin actions -> append-only audit log.
"""

import time

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from sonavault.db import SessionLocal
from sonavault.main import create_app
from sonavault.models.auth import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _next_totp_code(secret: str, *, after_step: int | None = None) -> str:
    """Returns a TOTP code guaranteed to be from a later 30s step than
    `after_step`, waiting out the current window if needed. Avoids flaky
    failures when two codes for the same secret are generated within the
    same 30-second step (which the replay guard correctly rejects)."""
    import asyncio

    totp = pyotp.TOTP(secret)
    while True:
        now = time.time()
        current_step = int(totp.timecode(now))
        if after_step is None or current_step > after_step:
            return totp.at(now)
        await asyncio.sleep(30 - (now % 30) + 0.5)


async def test_register_and_login(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "e2e-basic@sanctuary.org", "password": "CorrectHorseBattery9"},
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "e2e-basic@sanctuary.org", "password": "CorrectHorseBattery9"},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "authenticated"
    assert body["access_token"]
    assert body["mfa_setup_required"] is False


async def test_login_rejects_wrong_password_and_unknown_user(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "e2e-wrong@sanctuary.org", "password": "CorrectHorseBattery9"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "e2e-wrong@sanctuary.org", "password": "totally-wrong-pw"},
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody-e2e@sanctuary.org", "password": "whatever12345"},
    )
    assert resp.status_code == 401


async def test_totp_enroll_confirm_then_mfa_required_login(client: AsyncClient):
    email = "e2e-totp@sanctuary.org"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
    )
    login = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    token = login["access_token"]

    enroll = (
        await client.post("/api/v1/mfa/totp/enroll", headers={"Authorization": f"Bearer {token}"})
    ).json()
    secret = enroll["secret"]
    confirm_step = int(pyotp.TOTP(secret).timecode(time.time()))
    code = pyotp.TOTP(secret).now()
    confirm = await client.post(
        "/api/v1/mfa/totp/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": code},
    )
    assert confirm.status_code == 200
    recovery_codes = confirm.json()["recovery_codes"]
    assert len(recovery_codes) == 10

    # Re-login now requires MFA.
    login2 = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    assert login2["status"] == "mfa_required"
    ticket = login2["mfa_ticket"]

    # Wrong code fails.
    bad = await client.post(
        "/api/v1/mfa/verify", json={"mfa_ticket": ticket, "method": "totp", "code": "000000"}
    )
    assert bad.status_code == 401

    fresh_code = await _next_totp_code(secret, after_step=confirm_step)
    good = await client.post(
        "/api/v1/mfa/verify", json={"mfa_ticket": ticket, "method": "totp", "code": fresh_code}
    )
    assert good.status_code == 200
    assert good.json()["status"] == "authenticated"

    # Replaying the same code in the same login attempt must fail.
    login3 = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    replay = await client.post(
        "/api/v1/mfa/verify",
        json={"mfa_ticket": login3["mfa_ticket"], "method": "totp", "code": fresh_code},
    )
    assert replay.status_code == 401

    # Recovery code works once, then is rejected on reuse.
    login4 = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    recovery_resp = await client.post(
        "/api/v1/mfa/verify",
        json={
            "mfa_ticket": login4["mfa_ticket"],
            "method": "recovery_code",
            "code": recovery_codes[0],
        },
    )
    assert recovery_resp.status_code == 200

    login5 = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    recovery_reuse = await client.post(
        "/api/v1/mfa/verify",
        json={
            "mfa_ticket": login5["mfa_ticket"],
            "method": "recovery_code",
            "code": recovery_codes[0],
        },
    )
    assert recovery_reuse.status_code == 401


async def test_refresh_rotation_and_reuse_detection(client: AsyncClient):
    email = "e2e-refresh@sanctuary.org"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
    )
    await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
    )
    pre_refresh_cookie = client.cookies.get("sv_refresh")
    assert pre_refresh_cookie

    first_refresh = await client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200
    rotated_cookie = client.cookies.get("sv_refresh")
    assert rotated_cookie != pre_refresh_cookie

    # Reuse of the stale pre-refresh token must fail and revoke the family.
    client.cookies.set("sv_refresh", pre_refresh_cookie)
    reuse_resp = await client.post("/api/v1/auth/refresh")
    assert reuse_resp.status_code == 401
    assert "reuse detected" in reuse_resp.json()["detail"].lower()

    # The legitimate rotated token must now ALSO be rejected (family revoked).
    client.cookies.set("sv_refresh", rotated_cookie)
    post_revocation_resp = await client.post("/api/v1/auth/refresh")
    assert post_revocation_resp.status_code == 401


async def test_rbac_401_vs_403_and_step_up_mfa(client: AsyncClient):
    email = "e2e-admin@sanctuary.org"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
    )
    login = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    viewer_token = login["access_token"]

    # No token at all -> 401.
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401

    # Valid token but insufficient role tier -> 403, not 401.
    resp = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert resp.status_code == 403

    # Promote directly in DB (simulating an existing admin having done this).
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.role = "security_admin"
        await session.commit()

    # Login after promotion must succeed (not deadlock) and flag MFA setup.
    login2 = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    assert login2["status"] == "authenticated"
    assert login2["mfa_setup_required"] is True
    admin_token_no_mfa = login2["access_token"]

    # Role tier check passes now, but step-up-gated role change fails
    # without a recent MFA verification.
    users = (
        await client.get(
            "/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token_no_mfa}"}
        )
    ).json()
    assert resp.status_code != 500
    target_id = next(u["id"] for u in users if u["email"] == email)

    role_change_no_stepup = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        headers={"Authorization": f"Bearer {admin_token_no_mfa}"},
        json={"role": "archivist"},
    )
    assert role_change_no_stepup.status_code == 403
    assert role_change_no_stepup.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    # Enroll MFA, re-login with it, then the step-up-gated action succeeds.
    enroll = (
        await client.post(
            "/api/v1/mfa/totp/enroll", headers={"Authorization": f"Bearer {admin_token_no_mfa}"}
        )
    ).json()
    secret = enroll["secret"]
    confirm_step = int(pyotp.TOTP(secret).timecode(time.time()))
    code = pyotp.TOTP(secret).now()
    await client.post(
        "/api/v1/mfa/totp/confirm",
        headers={"Authorization": f"Bearer {admin_token_no_mfa}"},
        json={"code": code},
    )

    login3 = (
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
        )
    ).json()
    fresh_code = await _next_totp_code(secret, after_step=confirm_step)
    verify = (
        await client.post(
            "/api/v1/mfa/verify",
            json={"mfa_ticket": login3["mfa_ticket"], "method": "totp", "code": fresh_code},
        )
    ).json()
    stepped_up_token = verify["access_token"]

    role_change_ok = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        headers={"Authorization": f"Bearer {stepped_up_token}"},
        json={"role": "archivist"},
    )
    assert role_change_ok.status_code == 200

    pii_unmask = await client.post(
        "/api/v1/admin/pii/unmask",
        headers={"Authorization": f"Bearer {stepped_up_token}"},
        json={"resource_type": "transcript", "resource_id": "abc123", "reason": "investigation"},
    )
    assert pii_unmask.status_code == 200

    # Append-only audit log recorded both sensitive actions.
    audit = (
        await client.get(
            "/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {stepped_up_token}"}
        )
    ).json()
    actions = {entry["action"] for entry in audit}
    assert "role_change" in actions
    assert "pii_unmask" in actions
