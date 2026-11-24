import pytest

from sonavault.core.provenance.ledger import NewEvent, append_event, verify_chain
from sonavault.db import SessionLocal

pytestmark = pytest.mark.asyncio


async def test_metadata_persisted_but_excluded_from_hash():
    sha256 = "d" * 64
    async with SessionLocal() as session:
        row_with_meta = await append_event(
            session,
            NewEvent(
                object_sha256=sha256,
                event_type="ingest",
                agent_id="tester",
                payload_sha256=sha256,
                metadata={"original_filename": "hydrophone.wav"},
            ),
        )
        await session.commit()
        assert row_with_meta.metadata_json == {"original_filename": "hydrophone.wav"}

        valid, broken_at = await verify_chain(session, sha256)
        assert valid
        assert broken_at is None
