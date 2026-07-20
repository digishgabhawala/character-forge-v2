# character-forge-v2

A local, no-training consistent character image generator. Give it a text
brief once, generate several hero candidates, lock the one you like as the
character's permanent reference -- then generate that same character doing
anything you describe, any number of times, with visual consistency (face,
body proportions, outfit, colors) held via reference-conditioned image
editing (Qwen-Image-Edit), not a fine-tuned model.

An earlier version of this pipeline (see the sibling `character-forge`
project) tried training a per-character LoRA instead. That was abandoned:
the trained LoRA was visibly lower quality than just editing off the raw
hero image directly, and required hours of GPU time per character. This
version generates every image fresh from the locked hero + a text
instruction -- more compute per image, zero training, and better quality.

## What this is for

This is a general-purpose character asset generator, not tied to any one
downstream use. Once a character is locked, "generate this character doing
X" can feed:

- reference frames for video generation or animation
- storyboard / storyline panels
- social media posts (any platform)
- consistent illustration for any product, doc, or presentation

One example consumer exists today: [`linkedin-content-agent`](../linkedin-content-agent),
a sibling project that calls this tool as a subprocess to illustrate
LinkedIn posts. It's just one caller among many possible ones -- this repo
has no dependency on it and no LinkedIn-specific logic.

## Prerequisites

- Python 3.10+
- A [ComfyUI](https://github.com/comfyanonymous/ComfyUI) install, running
  and reachable (default `http://127.0.0.1:8188`), with the model files
  below present.

**Installing ComfyUI**, if you don't already have it:
```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3 -m venv .venv          # or reuse an existing venv
.venv/bin/pip install -r requirements.txt
# ComfyUI-GGUF custom node (required -- provides the GGUF-quantized model
# loaders this pipeline's workflows use):
git clone https://github.com/city96/ComfyUI-GGUF.git custom_nodes/ComfyUI-GGUF
.venv/bin/pip install -r custom_nodes/ComfyUI-GGUF/requirements.txt
.venv/bin/python main.py       # starts the server on :8188
```

**Downloading the models** (~34 GB, GGUF-quantized -- see "Why GGUF" below):
```bash
cd character-forge-v2
pip install -e .
forge2 download --comfy-dir /path/to/ComfyUI/models
```
This fetches, into the right `ComfyUI/models/` subfolders: the Qwen-Image
and Qwen-Image-Edit UNets (Q4_K_M GGUF), the Qwen2.5-VL text encoder +
its vision projector, the VAE, and two optional Lightning speed-up LoRAs.
Resumable, skips files already present. Exact repos/filenames are in
`forge2/config.py`.

### Why GGUF quantization

Qwen-Image-Edit is a ~20B-parameter model -- at full precision that's
40GB+, more than most consumer machines have. The GGUF-quantized version
(`Q4_K_M`, ~10GB) is what makes it fit. This project was built and tested
on **Apple Silicon (M-series Mac, unified memory)**, where GGUF is close to
necessary. ComfyUI itself is cross-platform (Linux/Windows, NVIDIA/AMD/CPU),
so this should work there too -- **not yet tested on anything but Mac.** On
a machine with a GPU that has enough VRAM for the full-precision or a
lighter (fp8/bf16) quantization, you could point the workflow JSONs
(`forge2/comfy_workflows/*.json`) at non-GGUF loader nodes instead; that's
a config change, not a code change, but hasn't been tried here.

### Does this run on a free-tier Colab notebook?

Probably, for **generation** -- untested, but plausible. Free-tier Colab
gives a T4 GPU (16GB VRAM), and these are exactly the memory-constrained
inference conditions GGUF quantization targets; ComfyUI runs natively on
CUDA. This is different from an earlier, separate attempt (in the sibling
`character-forge` project) to *train* a LoRA on Colab free tier, which
failed -- training needs gradients + optimizer state on top of the model
weights, a much heavier memory profile than pure inference. This repo does
no training at all, so that specific failure doesn't apply here. If you try
it, this note should be updated with the real result.

## Setup

**One venv is enough for both ComfyUI and `forge2`** -- if you already have
a venv with ComfyUI's dependencies installed (e.g. the one from
"Installing ComfyUI" above), reuse it here instead of creating a second one:

```bash
cd character-forge-v2
/path/to/existing/venv/bin/pip install -e .
```

Or keep them separate, if you'd rather:
```bash
cd character-forge-v2
python3 -m venv .venv
.venv/bin/pip install -e .
```

Either way, confirm it worked: `<venv>/bin/forge2 --help` should list
`download`, `concept`, `pick-hero`, `generate`.

### Every time you want to use this, start here

1. **Start ComfyUI** in its own terminal, and leave it running for the
   whole session -- `concept`/`pick-hero`/`generate` all talk to it over
   HTTP and fail immediately if it's not reachable:
   ```bash
   cd /path/to/ComfyUI
   /path/to/venv/bin/python main.py
   # wait for "Starting server" in the logs -- reachable at http://127.0.0.1:8188
   ```
2. **Activate your venv**, in a second terminal, for running `forge2`
   commands:
   ```bash
   source /path/to/venv/bin/activate
   forge2 --help
   ```

No need to restart ComfyUI between `forge2` commands -- only if it gets
into a bad state (see Known issues below).

## Configuration

`configs/default.yaml` is the single config file:

| Key | Default | What it does |
|---|---|---|
| `workspace` | `./workspace` | where character folders live |
| `comfy.url` | `http://127.0.0.1:8188` | ComfyUI server |
| `comfy.comfy_models_dir` | *(unset)* | path to `ComfyUI/models`, used by `forge2 download` |
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
  exact `subprocess.Popen(...)` invocation) -- but any caller can use the
  same mechanism.

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
- All of the above (RAM pressure, corrupted output) was diagnosed on Mac.
  Behavior on a real dedicated-VRAM GPU (Colab, a Linux box with an NVIDIA
  card) is untested and may differ, for better or worse.

## Upcoming / backlog (not built yet)

- **Pre-flight RAM check** before starting a render -- warn or abort if free
  RAM is too low, instead of silently producing a corrupted black image.
- **Automatic corrupted-image detection + auto-restart ComfyUI** -- detect a
  degenerate (e.g. near-uniform-color) output and automatically restart the
  ComfyUI process and retry, rather than requiring a human to notice and
  intervene.
- **Manage the ComfyUI process internally** -- start it (and stop it when
  idle) as part of this tool's own lifecycle, instead of requiring the
  caller to have it already running on a known port. Would make setup
  simpler for any consumer (no separate terminal, no port coordination) at
  the cost of this tool owning a chunk of process-management complexity it
  doesn't have today.
- **Verify (or fix) portability off Mac** -- Linux/NVIDIA and free-tier
  Colab are both plausible but genuinely untested; see the notes above.

## Project layout

```
forge2/
  cli.py                    -- download / concept / pick-hero / generate commands
  config.py                 -- ForgeConfig (comfy/gen/concept sections)
  schemas.py                -- CharacterCard, CandidateMeta, workspace_layout()
  backend.py, comfy_backend.py  -- ComfyUI HTTP client
  prompts/templates.py      -- hero + generate instruction prompt builders
  comfy_workflows/*.json    -- ComfyUI API workflow graphs (GGUF-quantized)
  stages/concept.py         -- run_concept(), pick_hero()
  stages/generate.py        -- run_generate() + callback support
scripts/download_models.py  -- fetches model files (used by `forge2 download`)
workspace/<character_id>/
  character.json            -- the character card (identity, locked)
  hero.png                  -- the locked reference image
  01_hero_candidates/       -- candidates generated during concept, kept for provenance
  generated/                -- output of every `generate` call (gitignored -- runtime output)
```
