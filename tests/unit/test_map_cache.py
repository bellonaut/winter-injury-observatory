"""Unit tests for map cache behavior."""
import json
import time
from pathlib import Path

from api.cache import LayerCache


def test_cache_set_and_get_fresh(tmp_path: Path):
    cache = LayerCache(ttl_seconds=3600, cache_dir=str(tmp_path / "cache"))
    cache.set("layer::demo", {"type": "FeatureCollection", "features": []})

    got = cache.get("layer::demo")
    assert got is not None
    assert got["fresh"] is True
    assert got["stale"] is False
    assert got["source"] in {"memory", "live", "disk"}


def test_cache_stale_return_when_allowed(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache = LayerCache(ttl_seconds=1, cache_dir=str(cache_dir))
    cache.set("layer::demo", {"type": "FeatureCollection", "features": []})
    time.sleep(1.2)

    stale = cache.get("layer::demo", allow_stale=True)
    assert stale is not None
    assert stale["fresh"] is False
    assert stale["stale"] is True


def test_cache_returns_none_when_stale_and_not_allowed(tmp_path: Path):
    cache = LayerCache(ttl_seconds=1, cache_dir=str(tmp_path / "cache"))
    cache.set("layer::demo", {"type": "FeatureCollection", "features": []})
    time.sleep(1.2)

    stale_rejected = cache.get("layer::demo", allow_stale=False)
    assert stale_rejected is None


def test_cache_disk_fallback(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": time.time(),
        "value": {"type": "FeatureCollection", "features": [{"type": "Feature"}]},
    }
    (cache_dir / "layer__demo.json").write_text(json.dumps(payload), encoding="utf-8")

    cache = LayerCache(ttl_seconds=3600, cache_dir=str(cache_dir))
    got = cache.get("layer::demo")
    assert got is not None
    assert got["source"] == "disk"
    assert got["value"]["type"] == "FeatureCollection"


def test_cache_stats_include_refresh_failures(tmp_path: Path):
    cache = LayerCache(ttl_seconds=3600, cache_dir=str(tmp_path / "cache"))
    cache.get("layer::missing")
    cache.mark_refresh_failure()
    cache.mark_refresh_failure()

    stats = cache.stats()
    assert stats["misses"] >= 1
    assert stats["refresh_failures"] == 2
