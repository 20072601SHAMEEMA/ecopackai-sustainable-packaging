"""
EcoPackAI - Response Cache
Module: Flask Backend - Performance

Thread-safe in-memory cache with time-to-live (TTL) and least-recently-used
(LRU) eviction. Identical /predict and /recommend requests are answered from
here instead of re-running the models and the database lookups.

Key = SHA-256 of (endpoint, request body in canonical JSON form, model
fingerprint, ranking-config fingerprint). Because the model and config
fingerprints are part of the key, a retrained model or a changed config
produces new keys automatically, so stale results are never served after an
upgrade. Entries also expire after CACHE_TTL_SECONDS, and an admin can clear
everything with POST /admin/cache/clear.

In-memory means one cache per server process. With several processes or
servers, the same get/set interface can be backed by Redis instead.
"""

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict


def make_key(endpoint: str, body, *fingerprints: str) -> str:
    """Stable key: the same request gives the same key, whatever the key order in the JSON."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256("|".join([endpoint, canonical, *fingerprints]).encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1024, enabled: bool = True, clock=time.monotonic):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.enabled = enabled
        self._clock = clock
        self._items = OrderedDict()            # key -> (expires_at, value)
        self._lock = threading.Lock()
        self.hits = self.misses = self.evictions = self.expirations = 0

    def get(self, key):
        """Return a copy of the cached value, or None if missing or expired."""
        if not self.enabled:
            return None
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            expires_at, value = item
            if self._clock() >= expires_at:
                del self._items[key]
                self.expirations += 1
                self.misses += 1
                return None
            self._items.move_to_end(key)       # mark as recently used
            self.hits += 1
            return copy.deepcopy(value)

    def set(self, key, value) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._items[key] = (self._clock() + self.ttl, copy.deepcopy(value))
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)  # drop the least recently used entry
                self.evictions += 1

    def clear(self) -> int:
        with self._lock:
            removed = len(self._items)
            self._items.clear()
            return removed

    def stats(self) -> dict:
        with self._lock:
            lookups = self.hits + self.misses
            return {"enabled": self.enabled, "entries": len(self._items), "max_entries": self.max_entries,
                    "ttl_seconds": self.ttl, "hits": self.hits, "misses": self.misses,
                    "hit_rate": round(self.hits / lookups, 4) if lookups else 0.0,
                    "evictions": self.evictions, "expirations": self.expirations}
