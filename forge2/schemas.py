"""Data contracts. Trimmed fork of character-forge/forge/schemas.py.

The CharacterCard is the DURABLE asset -- unchanged in shape from v1 so
existing character.json files (e.g. gtee_dev's) load without migration.
CandidateMeta/workspace_layout are trimmed to what concept+generate need.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Character card
# ---------------------------------------------------------------------------

class SignatureAttribute(BaseModel):
    """One of the <=3 things that make the character instantly recognizable.

    Keep these BIG and SIMPLE (a green tee, round glasses, spiky hair).
    Small/precise marks (logos, text) do NOT belong here -- they get
    composited deterministically in post, never diffused.
    """
    name: str                      # e.g. "green t-shirt"
    prompt_phrase: str             # exact phrase used in every prompt
    color_hex: Optional[str] = None  # for palette-drift QC, e.g. "#2E8B57"


class CharacterCard(BaseModel):
    """The single source of truth for a character. Survives model upgrades."""
    character_id: str              # slug, e.g. "gtee_dev"
    trigger_token: str             # historical field from LoRA-training era; unused by v2
    display_name: str = ""
    style_tag: str = "flat vector cartoon mascot"   # global art-style phrase
    species_or_type: str = "human"                  # human / animal / robot ...
    base_description: str = ""     # one-sentence identity used in every prompt
    signature_attributes: list[SignatureAttribute] = Field(default_factory=list)
    personality: str = ""          # e.g. "the skeptic; dry humor" (consumed by
    #                                the LinkedIn content agent, not by this pipeline)
    negative_traits: str = ""      # things to keep OUT of prompts/images
    hero_image: Optional[str] = None   # relative path once selected
    created_at: str = Field(default_factory=_now)
    notes: str = ""

    # -- persistence -------------------------------------------------------
    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> "CharacterCard":
        return cls.model_validate_json(path.read_text())

    # -- prompt helpers ----------------------------------------------------
    def identity_phrase(self) -> str:
        """The invariant identity chunk injected into EVERY prompt."""
        attrs = ", ".join(a.prompt_phrase for a in self.signature_attributes)
        bits = [self.base_description, attrs]
        return ", ".join(b for b in bits if b)


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

class CandidateMeta(BaseModel):
    """Sidecar metadata for every generated image (hero candidates and
    production generate-stage renders)."""
    filename: str
    kind: Literal["hero_candidate", "generated"]
    character_id: str
    seed: int
    prompt: str                    # full prompt / edit instruction actually sent
    source_image: Optional[str] = None   # hero path for edits
    model_id: str = ""
    steps: int = 0
    guidance: float = 0.0
    created_at: str = Field(default_factory=_now)

    def sidecar_path(self, images_dir: Path) -> Path:
        return images_dir / (Path(self.filename).stem + ".json")

    def save(self, images_dir: Path) -> None:
        self.sidecar_path(images_dir).write_text(self.model_dump_json(indent=2))


class StageManifest(BaseModel):
    """Written by every stage into its output dir. Makes runs resumable
    and auditable."""
    stage: str
    character_id: str
    started_at: str = Field(default_factory=_now)
    finished_at: Optional[str] = None
    config_snapshot: dict = Field(default_factory=dict)
    items: list[str] = Field(default_factory=list)   # filenames produced
    stats: dict = Field(default_factory=dict)

    def finish(self, path: Path) -> None:
        self.finished_at = _now()
        path.write_text(self.model_dump_json(indent=2))


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def workspace_layout(root: Path, character_id: str) -> dict[str, Path]:
    """Canonical on-disk layout for one character. Trimmed to what
    concept+generate need -- no candidates/dataset/lora_out/validation dirs."""
    base = root / character_id
    return {
        "base": base,
        "card": base / "character.json",
        "hero_candidates": base / "01_hero_candidates",
        "hero": base / "hero.png",
        "generated": base / "generated",
    }


def ensure_dirs(layout: dict[str, Path]) -> None:
    for key, p in layout.items():
        if key in ("card", "hero"):
            continue
        p.mkdir(parents=True, exist_ok=True)
