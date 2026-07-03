"""Content-addressed output cache (SHA-256 of the request).

Identical requests reuse a cached result instead of re-calling the (paid) API.
Cache lives in <repo>/.cache (gitignored). Each node exposes a `use_cache`
toggle. The API key is never part of the key.
"""

import hashlib
import json
import os

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")


def make_key(node: str, params: dict, image_bytes=None) -> str:
    """SHA-256 over node name + params (canonical JSON) + input image bytes."""
    h = hashlib.sha256()
    h.update(node.encode("utf-8"))
    h.update(json.dumps(params, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    for b in (image_bytes or []):
        h.update(hashlib.sha256(b).digest())
    return h.hexdigest()


def path_for(key: str, ext: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.{ext}")


def load(key: str, ext: str):
    try:
        with open(path_for(key, ext), "rb") as f:
            return f.read()
    except OSError:
        return None


def save(key: str, ext: str, data: bytes) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path_for(key, ext), "wb") as f:
        f.write(data)
