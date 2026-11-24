import uuid

import pytest

from sonavault.core.assets.scoping import (
    AssetNotFoundError,
    AssetOutOfScopeError,
    get_scoped_asset,
)
from sonavault.core.security.current_user import CurrentUser
from sonavault.db import SessionLocal
from sonavault.models.assets import Asset


def _viewer(sanctuary_scopes: list[str]) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        role="viewer",
        sanctuary_scopes=sanctuary_scopes,
        amr=["pwd"],
        mfa_verified_at=None,
    )


def _archivist() -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        role="archivist",
        sanctuary_scopes=[],
        amr=["pwd"],
        mfa_verified_at=None,
    )


@pytest.mark.asyncio
async def test_raises_not_found_for_missing_asset():
    async with SessionLocal() as session:
        with pytest.raises(AssetNotFoundError):
            await get_scoped_asset(session, sha256="f" * 64, user=_viewer([]))


@pytest.mark.asyncio
async def test_unscoped_asset_visible_to_everyone():
    sha256 = uuid.uuid4().hex + uuid.uuid4().hex
    async with SessionLocal() as session:
        session.add(Asset(sha256=sha256, asset_type="audio", mime_type="audio/wav", size_bytes=1))
        await session.commit()

        asset = await get_scoped_asset(session, sha256=sha256, user=_viewer([]))
        assert asset.sha256 == sha256


@pytest.mark.asyncio
async def test_scoped_asset_rejected_when_out_of_scope():
    sha256 = uuid.uuid4().hex + uuid.uuid4().hex
    async with SessionLocal() as session:
        session.add(
            Asset(
                sha256=sha256,
                asset_type="audio",
                mime_type="audio/wav",
                size_bytes=1,
                sanctuary_id="RESTRICTED_ZONE",
            )
        )
        await session.commit()

        with pytest.raises(AssetOutOfScopeError):
            await get_scoped_asset(session, sha256=sha256, user=_viewer(["OC02"]))


@pytest.mark.asyncio
async def test_scoped_asset_allowed_when_in_scope():
    sha256 = uuid.uuid4().hex + uuid.uuid4().hex
    async with SessionLocal() as session:
        session.add(
            Asset(
                sha256=sha256,
                asset_type="audio",
                mime_type="audio/wav",
                size_bytes=1,
                sanctuary_id="OC02",
            )
        )
        await session.commit()

        asset = await get_scoped_asset(session, sha256=sha256, user=_viewer(["OC02"]))
        assert asset.sha256 == sha256


@pytest.mark.asyncio
async def test_archivist_bypasses_scope_check():
    sha256 = uuid.uuid4().hex + uuid.uuid4().hex
    async with SessionLocal() as session:
        session.add(
            Asset(
                sha256=sha256,
                asset_type="audio",
                mime_type="audio/wav",
                size_bytes=1,
                sanctuary_id="RESTRICTED_ZONE",
            )
        )
        await session.commit()

        asset = await get_scoped_asset(session, sha256=sha256, user=_archivist())
        assert asset.sha256 == sha256
