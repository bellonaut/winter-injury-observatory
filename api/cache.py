"""Simple TTL cache with in-memory + disk-backed fallback for map layers."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """Represents one cached object."""

    value: Dict[str, Any]
    fetched_at: float

    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.fetched_at)

    def is_fresh(self, ttl_seconds: int) -> bool:
        return self.age_seconds() <= ttl_seconds


class LayerCache:
    """Layer cache with hourly TTL and stale fallback support."""

    def __init__(self, ttl_seconds: int = 3600, cache_dir: str = ".cache/map"):
        self.ttl_seconds = int(ttl_seconds)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "stale_hits": 0,
            "writes": 0,
            "refresh_failures": 0,
        }

    def _path_for_key(self, key: str) -> Path:
        sanitized = "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in key)
        return self.cache_dir / f"{sanitized}.json"

    def _load_disk_entry(self, key: str) -> Optional[CacheEntry]:
        path = self._path_for_key(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            value = payload.get("value")
            fetched_at = float(payload.get("fetched_at", 0))
            if not isinstance(value, dict) or fetched_at <= 0:
                return None
            return CacheEntry(value=value, fetched_at=fetched_at)
        except Exception:
            return None

    def get(self, key: str, allow_stale: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get a cache entry with freshness metadata.

        Returns:
            Dict containing `value`, `fresh`, `stale`, `age_seconds`, `fetched_at`, `source`
            or None if no usable cache entry is available.
        """
        with self._lock:
            entry = self._memory.get(key)

        source = "memory"
        if entry is None:
            entry = self._load_disk_entry(key)
            if entry is not None:
                with self._lock:
                    self._memory[key] = entry
                source = "disk"

        if entry is None:
            with self._lock:
                self._stats["misses"] += 1
            return None

        fresh = entry.is_fresh(self.ttl_seconds)
        if fresh:
            with self._lock:
                self._stats["hits"] += 1
        else:
            with self._lock:
                self._stats["stale_hits"] += 1
            if not allow_stale:
                return None

        return {
            "value": entry.value,
            "fresh": fresh,
            "stale": not fresh,
            "age_seconds": round(entry.age_seconds(), 3),
            "fetched_at": entry.fetched_at,
            "source": source,
        }

    def set(self, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        """Store entry in memory and disk cache."""
        now = time.time()
        entry = CacheEntry(value=value, fetched_at=now)

        with self._lock:
            self._memory[key] = entry
            self._stats["writes"] += 1

        payload = {"fetched_at": now, "value": value}
        path = self._path_for_key(key)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {
            "value": value,
            "fresh": True,
            "stale": False,
            "age_seconds": 0.0,
            "fetched_at": now,
            "source": "live",
        }

    def mark_refresh_failure(self):
        with self._lock:
            self._stats["refresh_failures"] += 1

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)
