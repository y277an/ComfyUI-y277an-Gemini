# ComfyUI-y277an-Gemini

ComfyUI custom node for **text-to-image** and **image editing** with Google
Gemini (Nano Banana / 2.5 Flash Image family).

> Uses your own Google AI Studio API key (billed to your Google account),
> not Comfy credits.

## Node

**Gemini Image (y277an)** — one node for both generation and editing:

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
- **Errors don't raise**: a grey placeholder image plus a `log` string are
  returned so the graph stays connected.

## Roadmap

- [x] system prompt / instruction input
- [x] top_p / top_k
- [x] safety settings toggle
- [x] publish to ComfyUI Registry

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
