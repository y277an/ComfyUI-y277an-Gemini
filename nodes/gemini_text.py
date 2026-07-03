"""Gemini Text node for ComfyUI.

Text generation with Google Gemini. One node covers two uses:
- No image -> text generation (e.g. expand a short idea into a rich image prompt).
- Attach an image -> vision (describe / caption / analyze it, or build a prompt
  from a reference image).

Output is a STRING you can feed into any node that takes text (e.g. a
CLIPTextEncode prompt, or our GeminiImage / Veo nodes).
"""

from . import _cache
from .gemini_image import _resolve_key, _tensor_png_bytes, _tensor_to_pil

DEFAULT_TEXT_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-2.5-pro",
    "gemini-flash-latest",
]

_TEXT_MODEL_CACHE = None

_EXCLUDE = ("image", "tts", "embedding", "veo", "live", "native-audio",
            "robotics", "computer-use")


def _list_text_models():
    """Live text-capable Gemini models (cached); falls back to a bundled list."""
    global _TEXT_MODEL_CACHE
    if _TEXT_MODEL_CACHE is not None:
        return _TEXT_MODEL_CACHE

    models = list(DEFAULT_TEXT_MODELS)
    key = _resolve_key("")
    if key:
        try:
            from google import genai

            client = genai.Client(api_key=key)
            fetched = []
            for m in client.models.list():
                short = (getattr(m, "name", "") or "").split("/")[-1]
                if "gemini" in short and not any(x in short for x in _EXCLUDE):
                    fetched.append(short)
            if fetched:
                models = fetched
        except Exception:
            pass

    _TEXT_MODEL_CACHE = models
    return models


class GeminiText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "Expand this into a detailed image-generation prompt: a blue cat running, happy",
                }),
                "model": (_list_text_models(),),
            },
            "optional": {
                "image": ("IMAGE",),
                "image2": ("IMAGE",),
                "system_prompt": ("STRING", {"multiline": True, "default": ""}),
                "api_key": ("STRING", {"default": ""}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "use_cache": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "generate"
    CATEGORY = "y277an/Gemini"

    def generate(self, prompt, model, image=None, image2=None, system_prompt="", api_key="", temperature=1.0, use_cache=True):
        key = _resolve_key(api_key)
        if not key:
            return ("ERROR: no API key (node api_key, config.json, or GEMINI_API_KEY env)",)

        input_images = [im for im in (image, image2) if im is not None]
        cache_params = {
            "prompt": prompt, "model": model,
            "system_prompt": system_prompt, "temperature": float(temperature),
        }
        cache_key = _cache.make_key(
            "GeminiText", cache_params, [_tensor_png_bytes(im) for im in input_images]
        )
        if use_cache:
            hit = _cache.load(cache_key, "txt")
            if hit is not None:
                return (hit.decode("utf-8"),)

        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            return (f"ERROR: google-genai not installed. pip install google-genai ({e})",)

        try:
            client = genai.Client(api_key=key)

            contents = [prompt]
            for im in input_images:
                contents.append(_tensor_to_pil(im))

            cfg = {"temperature": float(temperature)}
            if system_prompt and system_prompt.strip():
                cfg["system_instruction"] = system_prompt.strip()

            resp = client.models.generate_content(
                model=model, contents=contents, config=types.GenerateContentConfig(**cfg)
            )

            text = (getattr(resp, "text", None) or "").strip()
            if not text:  # fallback: gather text parts manually
                parts = []
                for c in (resp.candidates or []):
                    for p in (getattr(getattr(c, "content", None), "parts", None) or []):
                        if getattr(p, "text", None):
                            parts.append(p.text)
                text = " ".join(parts).strip()

            if use_cache and text:
                _cache.save(cache_key, "txt", text.encode("utf-8"))
            return (text or "(no text returned)",)

        except Exception as e:
            return (f"ERROR: {type(e).__name__}: {str(e)[:400]}",)
