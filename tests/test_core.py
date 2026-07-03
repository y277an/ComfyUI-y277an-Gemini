"""Unit tests for the pure logic (no network, no torch)."""

import pytest

import _cache
import _models
import _util


# ---- _cache.make_key ----

def test_make_key_is_order_independent():
    assert _cache.make_key("N", {"x": 1, "y": 2}) == _cache.make_key("N", {"y": 2, "x": 1})


def test_make_key_sensitive_to_params():
    assert _cache.make_key("N", {"x": 1}) != _cache.make_key("N", {"x": 2})


def test_make_key_sensitive_to_node_name():
    assert _cache.make_key("A", {"x": 1}) != _cache.make_key("B", {"x": 1})


def test_make_key_includes_image_bytes():
    assert _cache.make_key("N", {}, [b"aaa"]) != _cache.make_key("N", {}, [b"bbb"])


# ---- _util.with_retries ----

def test_retry_returns_result():
    assert _util.with_retries(lambda: 42) == 42


def test_retry_transient_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("503 UNAVAILABLE")
        return "ok"

    assert _util.with_retries(flaky, base_delay=0) == "ok"
    assert calls["n"] == 3


def test_retry_non_transient_raises_immediately():
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise ValueError("INVALID_ARGUMENT: bad prompt")

    with pytest.raises(ValueError):
        _util.with_retries(bad, base_delay=0)
    assert calls["n"] == 1  # not retried


# ---- _models disk cache ----

def test_models_load_cached_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setattr(_cache, "CACHE_DIR", str(tmp_path))
    assert _models.load_cached("image", ["default-x"]) == ["default-x"]


def test_models_refresh_then_load(tmp_path, monkeypatch):
    monkeypatch.setattr(_cache, "CACHE_DIR", str(tmp_path))

    class _M:
        def __init__(self, name):
            self.name = name

    class _Client:
        class models:
            @staticmethod
            def list():
                return [_M("models/veo-x"), _M("models/gemini-2.5-flash")]

    _models.refresh("veo", _Client(), lambda n: "veo" in n)
    assert _models.load_cached("veo", ["fallback"]) == ["veo-x"]
