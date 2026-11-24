"""Shared asset-level RBAC scoping check: below Archivist tier, a user may
only act on an asset that is either unscoped (sanctuary_id is None) or
within one of their own sanctuary_scopes.

Used by every slice that reads or mutates per-asset resources (ingest,
documents, transcripts, acoustics) so the rule lives in exactly one place.
"""

from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.security.rbac import ROLE_TIERS, CurrentUser
from sonavault.models.assets import Asset


class AssetAccessError(Exception):
    pass


class AssetNotFoundError(AssetAccessError):
    pass


class AssetOutOfScopeError(AssetAccessError):
    pass


async def get_scoped_asset(db: AsyncSession, *, sha256: str, user: CurrentUser) -> Asset:
    asset = await db.get(Asset, sha256)
    if asset is None:
        raise AssetNotFoundError(f"Asset {sha256} not found")
    if (
        user.tier < ROLE_TIERS["archivist"]
        and asset.sanctuary_id is not None
        and asset.sanctuary_id not in user.sanctuary_scopes
    ):
        raise AssetOutOfScopeError(f"Out of sanctuary scope for asset {sha256}")
    return asset


def raise_http_for_asset_error(exc: AssetAccessError) -> NoReturn:
    """Shared router-layer translation of AssetAccessError -> HTTPException,
    used by every slice that calls get_scoped_asset."""
    status_code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, AssetNotFoundError)
        else status.HTTP_403_FORBIDDEN
    )
    raise HTTPException(status_code, str(exc)) from exc
