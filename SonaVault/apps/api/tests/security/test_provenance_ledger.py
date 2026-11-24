from sonavault.core.provenance.ledger import GENESIS_HASH, compute_event_hash


def test_event_hash_is_deterministic():
    fields = {
        "object_sha256": "a" * 64,
        "event_type": "ingest",
        "agent_id": "x",
        "payload_sha256": "b" * 64,
    }
    h1 = compute_event_hash(prev_event_hash=GENESIS_HASH, event_fields=fields)
    h2 = compute_event_hash(prev_event_hash=GENESIS_HASH, event_fields=fields)
    assert h1 == h2
    assert len(h1) == 64


def test_event_hash_changes_with_prev_hash():
    fields = {
        "object_sha256": "a" * 64,
        "event_type": "ingest",
        "agent_id": "x",
        "payload_sha256": "b" * 64,
    }
    h1 = compute_event_hash(prev_event_hash=GENESIS_HASH, event_fields=fields)
    h2 = compute_event_hash(prev_event_hash="f" * 64, event_fields=fields)
    assert h1 != h2
