"""CurrentUser value object and role-tier table.

Split out from rbac.py so both rbac.py (guards) and deps.py (the Bearer-token
decoder that populates CurrentUser) can import it without creating a circular
import between the two.
"""

ROLE_TIERS: dict[str, int] = {
    "viewer": 1,
    "field_contributor": 2,
    "acoustic_analyst": 3,
    "archivist": 4,
    "security_admin": 5,
}


class CurrentUser:
    def __init__(
        self,
        *,
        user_id: str,
        role: str,
        sanctuary_scopes: list[str],
        amr: list[str],
        mfa_verified_at: float | None,
        sid: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.role = role
        self.sanctuary_scopes = sanctuary_scopes
        self.amr = amr
        self.mfa_verified_at = mfa_verified_at
        self.sid = sid

    @property
    def tier(self) -> int:
        return ROLE_TIERS.get(self.role, 0)
