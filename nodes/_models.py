"""Model-list cache that keeps network calls OUT of the UI-load path.

INPUT_TYPES (called when ComfyUI loads the node list) must not block on the
network. So the dropdown is filled from a disk cache (or a bundled default) with
no network call. The live list is refreshed opportunistically from generate()
— where we're already talking to the API — throttled by a TTL.
"""

import json
import os
import time

try:
    from . import _cache          # normal (package) import inside ComfyUI
except ImportError:               # allow standalone import (e.g. unit tests)
    import _cache

_TTL = 86400  # refresh the model list at most once per day


def _path(kind: str) -> str:
    return os.path.join(_cache.CACHE_DIR, f"models_{kind}.json")


def load_cached(kind: str, default: list) -> list:
    """Return the disk-cached model list (no network); fall back to default."""
    try:
        with open(_path(kind), "r", encoding="utf-8") as f:
            models = json.load(f).get("models")
        if models:
            return models
    except OSError:
        pass
    return list(default)


def refresh(kind: str, client, keep) -> None:
    """If the disk cache is stale/missing, fetch the live list and store it.
    Best-effort: called from generate() (network already in use); never raises.
    """
    p = _path(kind)
    try:
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < _TTL:
            return
    except OSError:
        pass
    try:
        models = [(getattr(m, "name", "") or "").split("/")[-1] for m in client.models.list()]
        models = [m for m in models if keep(m)]
        if models:
            os.makedirs(_cache.CACHE_DIR, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"models": models, "ts": time.time()}, f)
    except Exception:
        pass
