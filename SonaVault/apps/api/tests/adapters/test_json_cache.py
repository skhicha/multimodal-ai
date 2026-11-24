import pytest

from sonavault.adapters.storage import json_cache


@pytest.fixture(autouse=True)
def _isolate_cache_root(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_CACHE_ROOT", str(tmp_path))
    json_cache.get_settings.cache_clear()
    yield
    json_cache.get_settings.cache_clear()


def test_write_then_read_roundtrip():
    etag = json_cache.write_projection(
        asset_sha256="a" * 64, view="transcript", payload={"segments": [1, 2, 3]}
    )
    result = json_cache.read_projection(asset_sha256="a" * 64, view="transcript")
    assert result is not None
    assert result["data"] == {"segments": [1, 2, 3]}
    assert result["etag"] == etag


def test_read_missing_projection_returns_none():
    assert json_cache.read_projection(asset_sha256="b" * 64, view="transcript") is None


def test_write_is_atomic_no_tmp_file_left_behind(tmp_path):
    json_cache.write_projection(asset_sha256="c" * 64, view="transcript", payload={"x": 1})
    projection_dir = tmp_path / "projections" / ("c" * 64)
    leftover_tmp_files = [p for p in projection_dir.iterdir() if ".tmp." in p.name]
    assert leftover_tmp_files == []


def test_etag_changes_when_payload_changes():
    etag1 = json_cache.write_projection(asset_sha256="d" * 64, view="v", payload={"n": 1})
    etag2 = json_cache.write_projection(asset_sha256="d" * 64, view="v", payload={"n": 2})
    assert etag1 != etag2
