"""Stage 1 -- concept: character brief -> N hero candidates -> human picks one.

Input : a character_brief.yaml (or any brief yaml)
Output: workspace/<id>/01_hero_candidates/*.png (+ .json sidecars)
        workspace/<id>/character.json

Then run: forge2 pick-hero <id> <candidate-filename>

Unchanged from character-forge/forge/stages/concept.py except import paths.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import yaml

from forge2.config import ForgeConfig
from forge2.schemas import (CandidateMeta, CharacterCard, SignatureAttribute,
                            StageManifest, ensure_dirs, workspace_layout)
from forge2.prompts.templates import build_hero_prompt

log = logging.getLogger("forge2.concept")


def card_from_brief(brief_path: Path) -> CharacterCard:
    data = yaml.safe_load(brief_path.read_text())
    attrs = [SignatureAttribute(**a) for a in data.get("signature_attributes", [])]
    return CharacterCard(
        character_id=data["character_id"],
        trigger_token=data.get("trigger_token", data["character_id"]),
        display_name=data.get("display_name", ""),
        style_tag=data.get("style_tag", "flat vector cartoon mascot"),
        species_or_type=data.get("species_or_type", "human"),
        base_description=data.get("base_description", ""),
        signature_attributes=attrs,
        personality=data.get("personality", ""),
        negative_traits=data.get("negative_traits", ""),
        notes=data.get("notes", ""),
    )


def run_concept(cfg: ForgeConfig, brief_path: Path,
                profile: str | None = None) -> Path:
    card = card_from_brief(brief_path)
    layout = workspace_layout(cfg.workspace_path, card.character_id)
    ensure_dirs(layout)
    card.save(layout["card"])

    prompt = build_hero_prompt(card)
    log.info("Hero prompt: %s", prompt)

    from forge2 import backend
    be = backend.get_t2i(cfg, profile=profile)
    manifest = StageManifest(stage="concept", character_id=card.character_id,
                             config_snapshot=cfg.concept.model_dump())
    try:
        for i in range(cfg.concept.num_candidates):
            seed = cfg.concept.base_seed + i
            fname = f"hero_{seed}.png"
            if (layout["hero_candidates"] / fname).exists():
                manifest.items.append(fname)
                log.info("  [%d/%d] %s (already exists, skipped)",
                         i + 1, cfg.concept.num_candidates, fname)
                continue
            img = be.generate(prompt=prompt, negative=cfg.gen.negative_prompt,
                              seed=seed, width=cfg.gen.width,
                              height=cfg.gen.height)
            img.save(layout["hero_candidates"] / fname)
            CandidateMeta(filename=fname, kind="hero_candidate",
                          character_id=card.character_id, seed=seed,
                          prompt=prompt, model_id=be.model_name,
                          steps=be.effective_steps, guidance=be.effective_cfg,
                          ).save(layout["hero_candidates"])
            manifest.items.append(fname)
            log.info("  [%d/%d] %s", i + 1, cfg.concept.num_candidates, fname)
    finally:
        be.close()

    manifest.finish(layout["hero_candidates"] / "manifest.json")
    log.info("Done. Review %s and run: forge2 pick-hero %s <filename>",
             layout["hero_candidates"], card.character_id)
    return layout["hero_candidates"]


def pick_hero(cfg: ForgeConfig, character_id: str, filename: str) -> Path:
    layout = workspace_layout(cfg.workspace_path, character_id)
    src = layout["hero_candidates"] / filename
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copy(src, layout["hero"])
    card = CharacterCard.load(layout["card"])
    card.hero_image = "hero.png"
    card.save(layout["card"])
    log.info("Hero locked: %s", layout["hero"])
    return layout["hero"]
