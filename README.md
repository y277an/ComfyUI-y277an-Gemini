# ComfyUI-y277an-Gemini

ComfyUI custom nodes for **image** (text-to-image, editing), **video**
(Veo text/image-to-video), **text** (prompt generation / image understanding),
and **speech** (TTS) with Google Gemini.

> Uses your own Google AI Studio API key (billed to your Google account),
> not Comfy credits.

## Nodes

### Gemini Image (y277an) — text-to-image and editing

- Attach an `image` (and optionally `image2` / `image3`) → **edit / compose**
- No image → **text-to-image**
- Outputs: `IMAGE` + `log` (mode / model / notes / errors)

| Input | Description |
|---|---|
| `prompt` | Generation / edit instruction |
| `model` | Gemini image model. Fetched live when a key is configured, else a bundled list |
| `seed` | Random seed (auto-folded to int32 for Gemini) |
| `image` / `image2` / `image3` (opt) | Input images; providing any switches to edit mode |
| `aspect_ratio` (opt) | `auto` or a fixed ratio (`1:1`, `16:9`, …) |
| `api_key` (opt) | Optional override; **leave empty to use config.json / env** |
| `temperature` (opt) | Sampling temperature |
| `system_prompt` (opt) | System instruction (style / constraints); sent only if non-empty |
| `top_p` / `top_k` (opt) | Sampling controls; `top_k=0` means unset |
| `enable_safety` (opt) | When off, relaxes safety filters (BLOCK_NONE) |
| `use_cache` (opt) | Reuse a cached result for identical requests (see Caching) |

### Gemini Veo Video (y277an) — text-to-video and image-to-video

- No image → **text-to-video**; attach an `image` → it becomes the **first frame**
- Outputs: `VIDEO` (connect to SaveVideo) + `log`
- Veo is a long-running async op (submit → poll) and is **preview-only and
  expensive** — a few-second clip can cost real money.

| Input | Description |
|---|---|
| `prompt` | Video description |
| `model` | Veo model (default `veo-3.1-fast-generate-preview`) |
| `image` (opt) | First frame → image-to-video |
| `api_key` (opt) | Leave empty to use config.json / env |
| `duration_seconds` / `aspect_ratio` / `resolution` / `negative_prompt` (opt) | Clip controls (resolution 720p/1080p) |
| `use_cache` (opt) | Reuse a cached mp4 for identical requests (see Caching) |

> The AI Studio (Developer API) rejects several Veo config fields (`seed`,
> `generate_audio`, `fps`, non-default `resolution`, …) — those are Vertex-only
> and intentionally not exposed here.

### Gemini Text (y277an) — prompt generation and image understanding

- No image → **text generation** (e.g. expand a short idea into a rich prompt)
- Attach an `image` → **vision** (describe / caption / analyze it)
- Output: `STRING` — feed it into CLIPTextEncode, or our Gemini Image / Veo nodes

| Input | Description |
|---|---|
| `prompt` | Instruction (e.g. "expand into a detailed image prompt") |
| `model` | Text model (live list, fallback bundled) |
| `image` / `image2` (opt) | Reference images for vision tasks |
| `system_prompt` (opt) | System instruction |
| `api_key` (opt) | Leave empty to use config.json / env |
| `temperature` (opt) | Sampling temperature |
| `use_cache` (opt) | Reuse a cached result for identical requests (see Caching) |

### Gemini TTS (y277an) — text-to-speech

- Text → `AUDIO` (connect to SaveAudio / PreviewAudio); 24 kHz mono
- Inputs: `text`, `model`, `voice` (prebuilt voices), `api_key` (opt), `use_cache` (opt)

## Install

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/y277an/ComfyUI-y277an-Gemini.git
/path/to/ComfyUI/python -m pip install google-genai pillow numpy

# set up your API key (recommended: config file, see "API key" below)
cd ComfyUI-y277an-Gemini
cp config.json.example config.json
# then edit config.json and paste your Google AI Studio key

# restart ComfyUI
```

Or use ComfyUI-Manager → "Install via Git URL" with this repo, then create
`config.json` as above.

## API key

Get one from [Google AI Studio](https://aistudio.google.com/app/apikey)
(billing must be enabled; the free tier does not allow image generation).

Three ways to provide it, in priority order:

1. The node's `api_key` field (note: this value is saved into the workflow
   JSON, so avoid it when sharing workflows).
2. **`config.json` in this node's folder** — recommended. Copy
   `config.json.example` to `config.json` and paste your key. It is
   gitignored and never written into a workflow.
3. Environment variable `GEMINI_API_KEY` or `GOOGLE_API_KEY`.

## Design notes

- **Lazy import** of `google-genai`: ComfyUI still boots if the dependency is
  missing; a clear error is returned at execution time.
- **No hardcoded single model name**: the dropdown is populated from
  `client.models.list()` when a key is available, with a bundled fallback.
- **Errors don't raise** (image/text): a placeholder plus a `log` string are
  returned so the graph stays connected.
- **Automatic retries**: transient errors (rate limit / 5xx) are retried with
  exponential backoff; real errors surface immediately.
- **Veo progress**: the video node drives the ComfyUI progress bar while polling
  so it doesn't look frozen, and its model list is fetched live too.

## Caching

Every node has a `use_cache` toggle (on by default). Identical requests
(same prompt / model / params / input images) reuse a cached result instead of
re-calling the paid API — the second run returns instantly and costs nothing.
Especially useful for the expensive Veo video node.

- Cache is a content-addressed store (SHA-256 of the request) under `.cache/`
  (gitignored). The API key is never part of the key.
- Turn `use_cache` off to force a fresh call.
- To vary results on purpose, change the prompt/params (or the image node's
  `seed`) — that produces a different key and a fresh generation.

## Roadmap

- [x] system prompt / instruction input
- [x] top_p / top_k
- [x] safety settings toggle
- [x] publish to ComfyUI Registry
- [x] Veo video node (text-to-video / image-to-video)
- [x] Gemini Text node (prompt generation / image understanding)
- [x] Gemini TTS node (text-to-speech)
- [x] output caching (skip re-calling the API for identical requests)
- [x] automatic retries on transient errors

Not planned:

- **candidate_count** — Gemini image models reject it ("Multiple candidates is
  not enabled for this model").
- **batch output** — no need; use ComfyUI's built-in run count (top-right) with
  a randomized seed to get N variations.

## Publishing (maintainers)

Releasing a new version to the Comfy Registry:

1. Bump `version` in `pyproject.toml`.
2. **Ensure `config.json` is NOT in the working tree before publishing** — it
   may hold a real API key and must never be uploaded. Move it aside for the
   publish, then restore it. (Do not rely on `.gitignore` for the upload.)
3. `comfy node publish --token <registry token>` (optionally `--changelog`).

## License

MIT
