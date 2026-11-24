import hashlib

import pytest

from sonavault.adapters.storage import blob_nvme


@pytest.fixture(autouse=True)
def _isolate_blob_root(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_BLOB_ROOT", str(tmp_path))
    blob_nvme.get_settings.cache_clear()
    yield
    blob_nvme.get_settings.cache_clear()


def test_put_get_roundtrip():
    data = b"hydrophone audio bytes"
    sha256 = blob_nvme.put(data)
    assert sha256 == hashlib.sha256(data).hexdigest()
    assert blob_nvme.exists(sha256)
    assert blob_nvme.get(sha256) == data


def test_put_is_idempotent_for_identical_content():
    data = b"same bytes twice"
    sha1 = blob_nvme.put(data)
    sha2 = blob_nvme.put(data)
    assert sha1 == sha2


def test_fixity_detects_corruption(tmp_path):
    data = b"original content"
    sha256 = blob_nvme.put(data)
    assert blob_nvme.verify_fixity(sha256)

    # Simulate bit rot: overwrite the stored blob's bytes directly.
    path = blob_nvme.path_for(sha256)
    with open(path, "wb") as f:
        f.write(b"corrupted content")

    assert not blob_nvme.verify_fixity(sha256)


def test_fixity_false_for_missing_blob():
    assert not blob_nvme.verify_fixity("f" * 64)
