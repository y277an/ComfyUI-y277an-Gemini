"""Gemini Image node for ComfyUI.

Text-to-image and image editing with Google Gemini (Nano Banana /
2.5 Flash Image family).

Design notes:
- Lazy import of google-genai: ComfyUI still boots if the dep is missing;
  a clear error is returned at execution time instead.
- API key resolution order: node field > config.json (in the node dir) >
  GEMINI_API_KEY env > GOOGLE_API_KEY env. Putting the key in config.json
  keeps it out of the saved workflow JSON.
- One node does both: attach an image => edit mode; no image => generate.
- Multiple input images supported (image, image2, image3) for composition.
- Model dropdown is fetched live via client.models.list() when a key is
  available at UI-load time, falling back to a bundled list otherwise.
- Seed is folded into int32 (Gemini's limit).
- On error, a placeholder image plus a log string are returned so the graph
  stays connected.
"""

import io
import json
import os

import numpy as np
import torch
from PIL import Image

from . import _cache, _models, _util

# Bundled fallback model list (used when live listing is unavailable).
DEFAULT_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3-pro-image-preview",
    "gemini-3-pro-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3.1-flash-image",
]

ASPECT_RATIOS = ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9"]

# Harm categories relaxed to BLOCK_NONE when safety is disabled.
# (The AI Studio / generativelanguage API accepts these standard categories;
# the HARM_CATEGORY_IMAGE_* variants are Vertex-only and rejected here.)
_HARM_CATEGORIES = [
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
]

# Repo root = parent of this file's "nodes/" dir.
_NODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_NODE_DIR, "config.json")

def _is_image_model(name: str) -> bool:
    return "gemini" in name and "image" in name


def _key_from_config() -> str:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return (json.load(f).get("api_key") or "").strip()
    except Exception:
        return ""


def _resolve_key(api_key: str) -> str:
    return (
        (api_key or "").strip()
        or _key_from_config()
        or os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
    )


def _list_models() -> list:
    """Model dropdown, read from disk cache (no network at UI-load time);
    falls back to DEFAULT_MODELS. Refreshed from generate()."""
    return _models.load_cached("image", DEFAULT_MODELS)


def _tensor_to_pil(image: "torch.Tensor") -> Image.Image:
    """ComfyUI IMAGE (torch [B,H,W,C] float 0..1) -> first frame as PIL."""
    arr = (image[0].cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _pil_to_tensor(pil: Image.Image) -> "torch.Tensor":
    """PIL.Image -> ComfyUI IMAGE (torch [1,H,W,C] float 0..1)."""
    arr = np.array(pil.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _tensor_png_bytes(image: "torch.Tensor") -> bytes:
    """First frame of a ComfyUI IMAGE as PNG bytes (for cache keys / storage)."""
    b = io.BytesIO()
    _tensor_to_pil(image).save(b, format="PNG")
    return b.getvalue()


def _placeholder() -> "torch.Tensor":
    """Grey placeholder so the IMAGE output is always a valid tensor."""
    return _pil_to_tensor(Image.new("RGB", (512, 512), (64, 64, 64)))


class GeminiImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "a photo of a cat"}),
                "model": (_list_models(),),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": {
                "image": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "aspect_ratio": (ASPECT_RATIOS, {"default": "auto"}),
                "api_key": ("STRING", {"default": ""}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "system_prompt": ("STRING", {"multiline": True, "default": ""}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "top_k": ("INT", {"default": 0, "min": 0, "max": 100}),
                "enable_safety": ("BOOLEAN", {"default": True}),
                "use_cache": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "log")
    FUNCTION = "generate"
    CATEGORY = "y277an/Gemini"

    def generate(
        self,
        prompt,
        model,
        seed,
        image=None,
        image2=None,
        image3=None,
        aspect_ratio="auto",
        api_key="",
        temperature=1.0,
        system_prompt="",
        top_p=0.95,
        top_k=0,
        enable_safety=True,
        use_cache=True,
    ):
        log = []

        key = _resolve_key(api_key)
        if not key:
            return (
                _placeholder(),
                "ERROR: no API key (node api_key field, config.json, or GEMINI_API_KEY env)",
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            return (
                _placeholder(),
                f"ERROR: google-genai not installed. Run: pip install google-genai ({e})",
            )

        try:
            client = genai.Client(api_key=key)
            _models.refresh("image", client, _is_image_model)

            # Attach any provided images -> edit mode; otherwise generate.
            contents = [prompt]
            input_images = [im for im in (image, image2, image3) if im is not None]
            for im in input_images:
                contents.append(_tensor_to_pil(im))
            log.append(f"mode: {'edit' if input_images else 'generate'} ({len(input_images)} input image(s))")

            # --- output cache: identical request -> reuse, skip the API call ---
            cache_params = {
                "prompt": prompt, "model": model, "seed": int(seed),
                "aspect_ratio": aspect_ratio, "temperature": float(temperature),
                "system_prompt": system_prompt, "top_p": float(top_p),
                "top_k": int(top_k), "enable_safety": bool(enable_safety),
            }
            cache_key = _cache.make_key(
                "GeminiImage", cache_params, [_tensor_png_bytes(im) for im in input_images]
            )
            if use_cache:
                hit = _cache.load(cache_key, "png")
                if hit is not None:
                    return (_pil_to_tensor(Image.open(io.BytesIO(hit))), "cache hit\n" + "\n".join(log))

            safe_seed = int(seed) % (2 ** 31)  # Gemini seed is int32
            config_kwargs = {
                "response_modalities": ["Text", "Image"],
                "temperature": float(temperature),
                "seed": safe_seed,
            }
            if system_prompt and system_prompt.strip():
                config_kwargs["system_instruction"] = system_prompt.strip()
            if top_p and float(top_p) > 0:
                config_kwargs["top_p"] = float(top_p)
            if top_k and int(top_k) > 0:
                config_kwargs["top_k"] = int(top_k)
            if aspect_ratio and aspect_ratio != "auto":
                config_kwargs["image_config"] = types.ImageConfig(aspect_ratio=aspect_ratio)
            if not enable_safety:
                config_kwargs["safety_settings"] = [
                    types.SafetySetting(category=c, threshold="BLOCK_NONE")
                    for c in _HARM_CATEGORIES
                ]
            config = types.GenerateContentConfig(**config_kwargs)

            resp = _util.with_retries(
                lambda: client.models.generate_content(model=model, contents=contents, config=config)
            )

            images, texts = [], []
            for cand in (resp.candidates or []):
                parts = getattr(getattr(cand, "content", None), "parts", None) or []
                for p in parts:
                    inline = getattr(p, "inline_data", None)
                    if inline and inline.data:
                        images.append(_pil_to_tensor(Image.open(io.BytesIO(inline.data))))
                    elif getattr(p, "text", None):
                        texts.append(p.text)

            if not images:
                return (_placeholder(), "ERROR: no image returned. Model text: " + (" ".join(texts)[:300]))

            # Batch only if sizes match; otherwise fall back to the first image.
            try:
                out = torch.cat(images, dim=0)
            except Exception:
                out = images[0]

            log.append(f"model={model} seed={safe_seed} returned {len(images)} image(s)")
            if aspect_ratio != "auto":
                log.append(f"aspect_ratio={aspect_ratio}")
            if texts:
                log.append("model note: " + " ".join(texts)[:200])
            if use_cache:
                _cache.save(cache_key, "png", _tensor_png_bytes(out))
            return (out, "\n".join(log))

        except Exception as e:
            return (_placeholder(), f"ERROR: {type(e).__name__}: {str(e)[:400]}")
