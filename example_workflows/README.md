# Example workflows

These are **API-format** workflows (the format you POST to ComfyUI's `/prompt`
endpoint, or load with a script). They document how each node connects.

| File | Nodes |
|---|---|
| `image_generate.json` | Gemini Image → Save Image (text-to-image) |
| `image_edit.json` | Load Image → Gemini Image → Save Image (editing) |
| `image_caption.json` | Load Image → Gemini Text (vision) → Preview (describe an image) |
| `veo_video.json` | Gemini Veo Video → Save Video |
| `tts.json` | Gemini TTS → Save Audio |

Set your API key via `config.json` (see the main README) so the empty `api_key`
fields fall back to it. To build these on the canvas instead, drop the matching
nodes and connect them the same way.
