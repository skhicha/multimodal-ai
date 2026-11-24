from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.adapters.storage import blob_nvme
from sonavault.adapters.storage.json_cache import read_projection, write_projection
from sonavault.core.assets.scoping import get_scoped_asset
from sonavault.core.security.rbac import CurrentUser
from sonavault.slices.documents.parsing import parse_docx, parse_pdf, parse_sanctsound_spl_xml


class WrongAssetTypeError(Exception):
    pass


async def get_document_chunks(db: AsyncSession, *, sha256: str, user: CurrentUser) -> list[dict]:
    asset = await get_scoped_asset(db, sha256=sha256, user=user)
    if asset.asset_type not in ("pdf", "docx"):
        raise WrongAssetTypeError("Asset is not a parseable document")

    cached = read_projection(asset_sha256=sha256, view="chunks")
    if cached is not None:
        return cached["data"]["chunks"]

    data = blob_nvme.get(sha256)
    parsed = parse_pdf(data) if asset.asset_type == "pdf" else parse_docx(data)
    chunks = [
        {"index": c.index, "text": c.text, "page_or_section": c.page_or_section} for c in parsed
    ]
    write_projection(asset_sha256=sha256, view="chunks", payload={"chunks": chunks})
    return chunks


async def get_telemetry_readings(db: AsyncSession, *, sha256: str, user: CurrentUser) -> list[dict]:
    asset = await get_scoped_asset(db, sha256=sha256, user=user)
    if asset.asset_type != "xml":
        raise WrongAssetTypeError("Asset is not an XML telemetry log")

    cached = read_projection(asset_sha256=sha256, view="telemetry")
    if cached is not None:
        return cached["data"]["readings"]

    data = blob_nvme.get(sha256)
    parsed = parse_sanctsound_spl_xml(data)
    readings = [
        {
            "timestamp": r.timestamp,
            "station_code": r.station_code,
            "broadband_db": r.broadband_db,
            "bands": r.bands,
        }
        for r in parsed
    ]
    write_projection(asset_sha256=sha256, view="telemetry", payload={"readings": readings})
    return readings
