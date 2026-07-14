"""Backend dispatcher -- stages call this, never a concrete backend.

    be = backend.get_t2i(cfg)                # or get_edit(cfg)
    img = be.generate(prompt=..., negative=..., seed=..., width=..., height=...)
    img = be.edit(image_path=..., instruction=..., negative=..., seed=...)
    be.close()

Steps/cfg come from the speed profile (full vs lightning) resolved here, so
stages stay ignorant of sampler math.

Trimmed fork of character-forge/forge/backend.py: comfy-only (the diffusers
alt backend was for CUDA boxes / a hypothetical training path that v2 no
longer needs).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


class Backend(Protocol):
    effective_steps: int
    effective_cfg: float
    model_name: str

    def generate(self, *, prompt: str, negative: str, seed: int,
                 width: int, height: int): ...
    def edit(self, *, image_path: Path, instruction: str, negative: str,
             seed: int): ...
    def close(self) -> None: ...


@dataclass
class Profile:
    name: str
    steps: int
    cfg: float
    use_lightning: bool


def resolve_profile(cfg, override: Optional[str] = None) -> Profile:
    name = override or cfg.gen.speed_profile
    if name == "lightning":
        return Profile("lightning", cfg.gen.steps_lightning,
                       cfg.gen.cfg_lightning, True)
    return Profile("full", cfg.gen.steps_full, cfg.gen.cfg_full, False)


def get_t2i(cfg, profile: Optional[str] = None) -> Backend:
    from forge2.comfy_backend import ComfyBackend
    p = resolve_profile(cfg, profile)
    return ComfyBackend(cfg, kind="t2i", profile=p)


def get_edit(cfg, profile: Optional[str] = None) -> Backend:
    from forge2.comfy_backend import ComfyBackend
    p = resolve_profile(cfg, profile)
    return ComfyBackend(cfg, kind="edit", profile=p)
