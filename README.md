# character-forge-v2

Mac-local, no-cloud consistent character image generator. Given one locked
"hero" reference image of a character, generates new on-brand illustrations
of that character doing anything you describe, via Qwen-Image-Edit over a
local ComfyUI server.

This is "System 1" in the two-system split with
[`linkedin-content-agent`](../linkedin-content-agent) ("System 2") -- that
project calls this one as a detached subprocess to render the character
image for each post. It also works standalone from the CLI for any other use
of consistent character art.

## Use cases

- Generate a locked, reusable mascot/character reference (`concept` +
  `pick-hero`) once per character.
- From then on, generate new illustrations of that character in any pose,
  setting, or action (`generate`) without ever retraining anything --
  character consistency comes from reference-conditioned image editing, not
  a fine-tuned LoRA. (An earlier LoRA-training approach was tried and
  abandoned -- see [character-forge](../character-forge)'s history for why:
  a trained klein-4B LoRA was visibly lower quality than just editing off the
  raw hero image with Qwen-Image-Edit directly.)
- Called by another app as a fire-and-forget subprocess via
  `--callback-url`/`--job-id`, so a caller never has to block a request
  thread on a 15-40 min render.

## Prerequisites

- Python 3.10+
- A local [ComfyUI](https://github.com/comfyanonymous/ComfyUI) install with
  these models present under `ComfyUI/models/` (see `forge2/config.py` for
  the exact repo/filename list -- these are large GGUF quantizations chosen
  to fit Apple Silicon unified memory):
  - `unet/qwen-image-2512-Q4_K_M.gguf` (text-to-image, used by `concept`)
  - `unet/qwen-image-edit-2511-Q4_K_M.gguf` (reference-conditioned edit, used
    by `generate`)
  - `text_encoders/Qwen2.5-VL-7B-Instruct-UD-Q4_K_XL.gguf` +
    `text_encoders/Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf`
  - `vae/qwen_image_vae.safetensors`
  - Optional: the two `lightx2v/Qwen-Image-Lightning` LoRAs, only needed for
    `--profile lightning` (fast, lower-quality drafts) -- `full` profile
    (default) doesn't need them.
- ComfyUI itself running and reachable (default `http://127.0.0.1:8188`):
  ```bash
  cd path/to/ComfyUI && python main.py
  ```

This repo shares its Python environment with the sibling `character-forge`
project (`../comfyui-env`) and shares the same ComfyUI models directory
(`../imgworks/ComfyUI/models`) -- no separate model download needed if
character-forge is already set up.

## Setup

```bash
cd character-forge-v2
../comfyui-env/bin/pip install -e .
```

Confirm it installed correctly:
```bash
../comfyui-env/bin/forge2 --help
# should list exactly three commands: concept, pick-hero, generate
```

## Configuration

`configs/default.yaml` is the single config file:

| Key | Default | What it does |
|---|---|---|
| `workspace` | `./workspace` | where character folders live |
| `comfy.url` | `http://127.0.0.1:8188` | ComfyUI server |
| `comfy.timeout_s` | `7200` (2h) | hard ceiling per render before giving up |
| `comfy.shift` | `3.1` | raise to 12-13 if outputs come out blurry/soft |
| `gen.speed_profile` | `full` | `full` = 40 steps, production quality; `lightning` = 8 steps, fast drafts (needs the lightning LoRAs) |
| `gen.negative_prompt` | see file | applied to every generation |
| `concept.num_candidates` | `12` | how many hero candidates to generate per brief |

Override any of these with `--config path/to/other.yaml` on any command, or
edit `configs/default.yaml` directly.

## How to run

**1. Create a character** (only needed once per new character -- `gtee_dev`
is already seeded in `workspace/gtee_dev/`, skip to step 3 to reuse it):

```bash
forge2 concept examples/character_brief.yaml
# generates N hero candidates into workspace/<id>/01_hero_candidates/
# -- open them, pick your favorite
forge2 pick-hero gtee_dev hero_1003.png
# locks that one as workspace/gtee_dev/hero.png, the source of truth
```

**2. Generate an image** of the locked character doing something:

```bash
forge2 generate gtee_dev "presenting a chart on a whiteboard, office" --seed 42
# -> workspace/gtee_dev/generated/gen_00042.png (15-40 min on Mac, this is
#    a real 20B-parameter model -- see Known issues below)
```

Useful flags:
- `--out my_image.png` -- custom output filename
- `--profile lightning` -- fast low-quality draft instead of full quality
- `--callback-url <url> --job-id <id>` -- POST `{job_id, ok, image_path|error}`
  to that URL when done, instead of blocking. This is how
  `linkedin-content-agent` uses it (see `image_service.py` there for the
  exact `subprocess.Popen(...)` invocation).

## Known issues / operational notes

- **Renders can come back solid black/corrupted with no error reported.**
  Root-caused twice during verification: (1) low free system RAM (Ollama or
  other apps holding memory) starves ComfyUI's VAE decode, which fails
  silently rather than erroring; (2) ComfyUI itself, after a very long
  uptime across many model load/unload cycles, appears to accumulate bad
  GPU/MPS state -- restarting the ComfyUI process resolved it. If a render
  looks wrong, check free RAM (`curl localhost:8188/system_stats`) and
  consider restarting ComfyUI before re-running.
- **A retry MUST use a fresh seed.** ComfyUI caches per-node outputs keyed on
  exact input values including seed -- resubmitting the same seed replays
  whatever was cached last time (including a corrupted result) in ~0ms with
  no real compute. `linkedin-content-agent`'s retry path handles this
  automatically; if driving `forge2 generate` directly, always change
  `--seed` on a retry.
- On timeout (`comfy.timeout_s` exceeded), the ComfyUI-side job is NOT
  cancelled, only the client gives up waiting -- it may keep running/cache
  its result in ComfyUI regardless.

## Upcoming / backlog (not built yet)

- **Pre-flight RAM check** before starting a render -- warn or abort if free
  RAM is too low, instead of silently producing a corrupted black image.
- **Automatic corrupted-image detection + auto-restart ComfyUI** -- detect a
  degenerate (e.g. near-uniform-color) output and automatically restart the
  ComfyUI process and retry, rather than requiring a human to notice and
  intervene.

## Project layout

```
forge2/
  cli.py                    -- concept / pick-hero / generate commands
  config.py                 -- ForgeConfig (comfy/gen/concept sections)
  schemas.py                -- CharacterCard, CandidateMeta, workspace_layout()
  backend.py, comfy_backend.py  -- ComfyUI HTTP client
  prompts/templates.py      -- hero + generate instruction prompt builders
  comfy_workflows/*.json    -- ComfyUI API workflow graphs (GGUF-quantized)
  stages/concept.py         -- run_concept(), pick_hero()
  stages/generate.py        -- run_generate() + callback support
workspace/<character_id>/
  character.json            -- the character card (identity, locked)
  hero.png                  -- the locked reference image
  01_hero_candidates/       -- candidates generated during concept, kept for provenance
  generated/                -- output of every `generate` call (gitignored -- runtime output)
```
