"""ComfyUI-y277an-Gemini: Google Gemini image nodes.

ComfyUI registers nodes by reading NODE_CLASS_MAPPINGS /
NODE_DISPLAY_NAME_MAPPINGS. To add another model later (e.g. Grok), drop a
new file under nodes/ and register it here.
"""

from .nodes.gemini_image import GeminiImage
from .nodes.gemini_text import GeminiText
from .nodes.gemini_tts import GeminiTTS
from .nodes.gemini_video import GeminiVeoVideo

NODE_CLASS_MAPPINGS = {
    "GeminiImage_y277an": GeminiImage,
    "GeminiText_y277an": GeminiText,
    "GeminiTTS_y277an": GeminiTTS,
    "GeminiVeoVideo_y277an": GeminiVeoVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeminiImage_y277an": "Gemini Image (y277an)",
    "GeminiText_y277an": "Gemini Text (y277an)",
    "GeminiTTS_y277an": "Gemini TTS (y277an)",
    "GeminiVeoVideo_y277an": "Gemini Veo Video (y277an)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
