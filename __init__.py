"""ComfyUI-y277an-Gemini: Google Gemini image nodes.

ComfyUI registers nodes by reading NODE_CLASS_MAPPINGS /
NODE_DISPLAY_NAME_MAPPINGS. To add another model later (e.g. Grok), drop a
new file under nodes/ and register it here.
"""

from .nodes.gemini_image import GeminiImage

NODE_CLASS_MAPPINGS = {
    "GeminiImage_y277an": GeminiImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeminiImage_y277an": "Gemini Image (y277an)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
