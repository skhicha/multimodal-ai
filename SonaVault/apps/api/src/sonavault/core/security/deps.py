"""Authenticated-request dependency: decodes the Bearer access token and
populates request.state.user so sonavault.core.security.rbac guards work."""

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sonavault.core.security.current_user import CurrentUser
from sonavault.core.security.jwt import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user = CurrentUser(
        user_id=payload["sub"],
        role=payload["role"],
        sanctuary_scopes=payload.get("sanctuary_scopes", []),
        amr=payload.get("amr", []),
        mfa_verified_at=payload.get("mfa_verified_at"),
        sid=payload.get("sid"),
    )
    request.state.user = user
    return user
