"""Config. One YAML drives the whole pipeline.

Trimmed fork of character-forge/forge/config.py: only what `concept` and
`generate` need. No diffusers backend, no expand/qc/curate/train/validate
config sections -- character-forge-v2 exposes exactly two capabilities:
(A) generate hero candidates from a prompt + lock one, (B) generate one
image from a locked hero + instruction.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# ComfyUI backend
# ---------------------------------------------------------------------------

class HFFile(BaseModel):
    """One downloadable model file: where it lives on HF, where ComfyUI
    expects it, and the filename the workflow will reference."""
    repo: str
    filename: str
    dest: str                      # subfolder under ComfyUI/models/
    save_as: str | None = None  # rename after download (mmproj prefix rule)
    optional: bool = False

    @property
    def local_name(self) -> str:
        return self.save_as or self.filename


class ComfyFiles(BaseModel):
    # Verified file set (unsloth Qwen-Image-2512 guide, Jan 2026):
    unet_t2i: HFFile = HFFile(
        repo="unsloth/Qwen-Image-2512-GGUF",
        filename="qwen-image-2512-Q4_K_M.gguf", dest="unet")
    unet_edit: HFFile = HFFile(
        repo="unsloth/Qwen-Image-Edit-2511-GGUF",
        filename="qwen-image-edit-2511-Q4_K_M.gguf", dest="unet")
    clip: HFFile = HFFile(
        repo="unsloth/Qwen2.5-VL-7B-Instruct-GGUF",
        filename="Qwen2.5-VL-7B-Instruct-UD-Q4_K_XL.gguf", dest="text_encoders")
    # vision tower: must share the text encoder's filename prefix
    clip_mmproj: HFFile = HFFile(
        repo="unsloth/Qwen2.5-VL-7B-Instruct-GGUF",
        filename="mmproj-BF16.gguf", dest="text_encoders",
        save_as="Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf")
    vae: HFFile = HFFile(
        repo="Comfy-Org/Qwen-Image_ComfyUI",
        filename="split_files/vae/qwen_image_vae.safetensors", dest="vae",
        save_as="qwen_image_vae.safetensors")
    # Lightning acceleration LoRAs (OPTIONAL -- filenames drift between
    # releases; if download 404s, check the repo page and update, or just
    # run with speed_profile: full).
    lightning_t2i: HFFile = HFFile(
        repo="lightx2v/Qwen-Image-Lightning",
        filename="Qwen-Image-Lightning-8steps-V1.1.safetensors",
        dest="loras", optional=True)
    lightning_edit: HFFile = HFFile(
        repo="lightx2v/Qwen-Image-Lightning",
        filename="Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors",
        dest="loras",
        save_as="Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors",
        optional=True)


class ComfyConfig(BaseModel):
    url: str = "http://127.0.0.1:8188"
    files: ComfyFiles = Field(default_factory=ComfyFiles)
    workflow_t2i: str = "forge2/comfy_workflows/t2i_gguf.json"
    workflow_edit: str = "forge2/comfy_workflows/edit_gguf.json"
    sampler: str = "euler"
    scheduler: str = "simple"
    # unsloth tip: if outputs come out blurry/bad, raise shift to 12-13
    shift: float = 3.1
    # where your ComfyUI/models lives; used by LoRA auto-copy.
    comfy_models_dir: str | None = None   # e.g. ~/ComfyUI/models
    timeout_s: int = 7200                    # per-image ceiling (Mac = slow ok)
    poll_s: float = 2.0


# ---------------------------------------------------------------------------
# Generation knobs
# ---------------------------------------------------------------------------

class GenConfig(BaseModel):
    width: int = 1024
    height: int = 1024
    # profiles: "full" = quality, "lightning" = fast drafts
    speed_profile: Literal["full", "lightning"] = "full"
    steps_full: int = 40
    cfg_full: float = 2.5
    steps_lightning: int = 8
    cfg_lightning: float = 1.0
    negative_prompt: str = (
        "photorealistic, 3d render, blurry, deformed anatomy, extra limbs, "
        "text, watermark, logos on clothing, brand logos, trademarks, "
        "inconsistent colors"
    )


class ConceptConfig(BaseModel):
    num_candidates: int = 12
    base_seed: int = 1000


class ForgeConfig(BaseModel):
    workspace: str = "./workspace"
    backend: Literal["comfy"] = "comfy"
    comfy: ComfyConfig = Field(default_factory=ComfyConfig)
    gen: GenConfig = Field(default_factory=GenConfig)
    concept: ConceptConfig = Field(default_factory=ConceptConfig)

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace).expanduser().resolve()


def load_config(path: str | Path = "configs/default.yaml") -> ForgeConfig:
    p = Path(path)
    if p.exists():
        data = yaml.safe_load(p.read_text()) or {}
        return ForgeConfig.model_validate(data)
    return ForgeConfig()
