"""Gemini Veo video node for ComfyUI.

Text-to-video and image-to-video with Google Veo (via the Gemini API).

Notes:
- Veo is an ASYNC / long-running operation: submit -> poll until done.
- Attach an `image` -> it is used as the first frame (image-to-video);
  otherwise pure text-to-video.
- Output is a ComfyUI `VIDEO` (wrap the returned mp4), connect it to SaveVideo.
- Veo is expensive and preview-only; generation takes tens of seconds.
- Errors raise (unlike the image node) since there is no meaningful
  placeholder video.
"""

import io
import os
import tempfile
import time

from . import _cache, _models, _util
from .gemini_image import _resolve_key, _tensor_png_bytes, _tensor_to_pil

VEO_MODELS = [
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-preview",
    "veo-3.1-lite-generate-preview",
]

VEO_ASPECT_RATIOS = ["16:9", "9:16"]
VEO_RESOLUTIONS = ["720p", "1080p"]


def _is_veo_model(name: str) -> bool:
    return "veo" in name.lower()


def _list_veo_models():
    """Veo model dropdown from disk cache (no network at UI-load); refreshed
    from generate()."""
    return _models.load_cached("veo", VEO_MODELS)

_POLL_INTERVAL = 10   # seconds between polls
_POLL_TIMEOUT = 360   # give up after this many seconds


class GeminiVeoVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "a cinematic shot of a fox running through a sunny meadow"}),
                "model": (_list_veo_models(),),
            },
            "optional": {
                "image": ("IMAGE",),   # first frame -> image-to-video
                "api_key": ("STRING", {"default": ""}),
                "duration_seconds": ("INT", {"default": 4, "min": 2, "max": 8}),
                "aspect_ratio": (VEO_ASPECT_RATIOS, {"default": "16:9"}),
                "resolution": (VEO_RESOLUTIONS, {"default": "720p"}),
                "negative_prompt": ("STRING", {"default": ""}),
                "use_cache": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "log")
    FUNCTION = "generate"
    CATEGORY = "y277an/Gemini"

    def generate(
        self,
        prompt,
        model,
        image=None,
        api_key="",
        duration_seconds=4,
        aspect_ratio="16:9",
        resolution="720p",
        negative_prompt="",
        use_cache=True,
    ):
        key = _resolve_key(api_key)
        if not key:
            raise RuntimeError("Gemini Veo: no API key (node api_key, config.json, or GEMINI_API_KEY env)")

        # --- output cache: identical request -> reuse the mp4, skip the (paid) call ---
        cache_params = {
            "prompt": prompt, "model": model,
            "duration_seconds": int(duration_seconds),
            "aspect_ratio": aspect_ratio, "resolution": resolution,
            "negative_prompt": negative_prompt,
        }
        img_bytes = [_tensor_png_bytes(image)] if image is not None else []
        cache_key = _cache.make_key("GeminiVeoVideo", cache_params, img_bytes)
        if use_cache and os.path.exists(_cache.path_for(cache_key, "mp4")):
            from comfy_api.input_impl import VideoFromFile
            return (VideoFromFile(_cache.path_for(cache_key, "mp4")), "cache hit")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        _models.refresh("veo", client, _is_veo_model)

        cfg = {
            "number_of_videos": 1,
            "duration_seconds": int(duration_seconds),
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        if negative_prompt and negative_prompt.strip():
            cfg["negative_prompt"] = negative_prompt.strip()
        config = types.GenerateVideosConfig(**cfg)

        # Optional first-frame image -> image-to-video.
        image_arg = None
        mode = "text-to-video"
        if image is not None:
            buf = io.BytesIO()
            _tensor_to_pil(image).save(buf, format="PNG")
            image_arg = types.Image(image_bytes=buf.getvalue(), mime_type="image/png")
            mode = "image-to-video"

        # Submit (long-running operation).
        op = _util.with_retries(
            lambda: client.models.generate_videos(
                model=model, prompt=prompt, image=image_arg, config=config
            )
        )

        # Progress bar (best-effort; needs the ComfyUI execution context).
        try:
            from comfy.utils import ProgressBar
            pbar = ProgressBar(100)
        except Exception:
            pbar = None

        # Poll until done. Veo has no % progress, so approximate by elapsed time.
        start = time.time()
        _est = 90.0  # rough expected seconds, just to move the bar
        while not op.done:
            if time.time() - start > _POLL_TIMEOUT:
                raise TimeoutError(f"Gemini Veo: timed out after {_POLL_TIMEOUT}s")
            time.sleep(_POLL_INTERVAL)
            op = client.operations.get(op)
            if pbar:
                pbar.update_absolute(min(int((time.time() - start) / _est * 100), 99), 100)
        if pbar:
            pbar.update_absolute(100, 100)

        # Extract the video.
        resp = getattr(op, "response", None) or getattr(op, "result", None)
        vids = getattr(resp, "generated_videos", None) or []
        if not vids:
            raise RuntimeError(f"Gemini Veo: no video returned ({op})")
        video = vids[0].video

        data = getattr(video, "video_bytes", None)
        if not data:
            client.files.download(file=video)  # populates video_bytes
            data = getattr(video, "video_bytes", None)
        if not data:
            raise RuntimeError("Gemini Veo: could not obtain video bytes")

        # Persist the mp4 (cache dir when caching, else a temp file) and wrap it.
        if use_cache:
            _cache.save(cache_key, "mp4", data)
            video_path = _cache.path_for(cache_key, "mp4")
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp.write(data)
            tmp.flush()
            tmp.close()
            video_path = tmp.name

        from comfy_api.input_impl import VideoFromFile

        took = int(time.time() - start)
        log = (
            f"{mode} | model={model} | {duration_seconds}s "
            f"{aspect_ratio} | {len(data)//1024} KB | ~{took}s"
        )
        return (VideoFromFile(video_path), log)
