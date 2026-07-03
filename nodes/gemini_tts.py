"""Gemini TTS node for ComfyUI.

Text-to-speech with Google Gemini TTS. Output is a ComfyUI `AUDIO` you can
connect to SaveAudio / PreviewAudio.
"""

import numpy as np
import torch

from . import _cache, _util
from .gemini_image import _resolve_key

TTS_MODELS = [
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
    "gemini-3.1-flash-tts-preview",
]

# Gemini's prebuilt voices.
VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]
VOICES_OFF = ["(none)"] + VOICES  # for the optional second speaker

_SAMPLE_RATE = 24000  # Gemini TTS returns 24 kHz 16-bit mono PCM


def _pcm_to_audio(data: bytes, sample_rate: int = _SAMPLE_RATE) -> dict:
    """PCM16 mono bytes -> ComfyUI AUDIO ({waveform:[1,1,T] float, sample_rate})."""
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    waveform = torch.from_numpy(arr.copy())[None, None, :]
    return {"waveform": waveform, "sample_rate": sample_rate}


def _silent_audio() -> dict:
    return {"waveform": torch.zeros(1, 1, 1), "sample_rate": _SAMPLE_RATE}


class GeminiTTS:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "Hello from Gemini."}),
                "model": (TTS_MODELS, {"default": TTS_MODELS[0]}),
                "voice": (VOICES, {"default": "Kore"}),
            },
            "optional": {
                "api_key": ("STRING", {"default": ""}),
                "use_cache": ("BOOLEAN", {"default": True}),
                "language_code": ("STRING", {"default": ""}),  # e.g. "en-US", "cmn-CN"; empty = auto
                # Multi-speaker: set a 2nd voice and write text as "Name: line".
                "speaker2_voice": (VOICES_OFF, {"default": "(none)"}),
                "speaker1_name": ("STRING", {"default": "Speaker1"}),
                "speaker2_name": ("STRING", {"default": "Speaker2"}),
            },
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "log")
    FUNCTION = "generate"
    CATEGORY = "y277an/Gemini"

    def generate(self, text, model, voice, api_key="", use_cache=True, language_code="",
                 speaker2_voice="(none)", speaker1_name="Speaker1", speaker2_name="Speaker2"):
        key = _resolve_key(api_key)
        if not key:
            return (_silent_audio(), "ERROR: no API key (node api_key, config.json, or GEMINI_API_KEY env)")

        multi = speaker2_voice and speaker2_voice != "(none)"
        cache_key = _cache.make_key("GeminiTTS", {
            "text": text, "model": model, "voice": voice, "language_code": language_code,
            "speaker2_voice": speaker2_voice if multi else "",
            "speaker1_name": speaker1_name if multi else "",
            "speaker2_name": speaker2_name if multi else "",
        })
        if use_cache:
            hit = _cache.load(cache_key, "pcm")
            if hit is not None:
                return (_pcm_to_audio(hit), "cache hit")

        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            return (_silent_audio(), f"ERROR: google-genai not installed ({e})")

        def _voice_cfg(name):
            return types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=name))

        try:
            client = genai.Client(api_key=key)
            speech_kwargs = {}
            if language_code and language_code.strip():
                speech_kwargs["language_code"] = language_code.strip()
            if multi:
                speech_kwargs["multi_speaker_voice_config"] = types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(speaker=speaker1_name or "Speaker1", voice_config=_voice_cfg(voice)),
                        types.SpeakerVoiceConfig(speaker=speaker2_name or "Speaker2", voice_config=_voice_cfg(speaker2_voice)),
                    ]
                )
            else:
                speech_kwargs["voice_config"] = _voice_cfg(voice)
            config = types.GenerateContentConfig(
                response_modalities=["Audio"],
                speech_config=types.SpeechConfig(**speech_kwargs),
            )
            resp = _util.with_retries(
                lambda: client.models.generate_content(model=model, contents=text, config=config)
            )

            data, rate = None, _SAMPLE_RATE
            for c in (resp.candidates or []):
                for p in (getattr(getattr(c, "content", None), "parts", None) or []):
                    inline = getattr(p, "inline_data", None)
                    if inline and inline.data:
                        data = inline.data
                        mt = getattr(inline, "mime_type", "") or ""
                        for seg in mt.split(";"):
                            if seg.strip().startswith("rate="):
                                try:
                                    rate = int(seg.split("rate=")[1])
                                except ValueError:
                                    pass
                        break
                if data:
                    break

            if not data:
                return (_silent_audio(), "ERROR: no audio returned")

            if use_cache:
                _cache.save(cache_key, "pcm", data)
            who = f"{voice}+{speaker2_voice}" if multi else voice
            return (_pcm_to_audio(data, rate),
                    f"model={model} voice={who} lang={language_code or 'auto'} | {len(data)//1024} KB @ {rate}Hz")

        except Exception as e:
            return (_silent_audio(), f"ERROR: {type(e).__name__}: {str(e)[:300]}")
