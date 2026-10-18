"""Production stage -- generate: hero + freeform instruction -> one image.

No LoRA. This is the reference-conditioned path: every call re-derives from
the locked hero.png via the edit model, the same mechanism `expand` used in
character-forge v1 to build a training dataset. Traded a one-time training
cost for a per-call edit cost -- worth it once a trained LoRA's quality
couldn't match the base edit model's (see character-forge's project memory,
2026-07-14 decision).

Output: workspace/<id>/generated/*.png (+ .json sidecar).

Callback support: pass callback_url/job_id (or --callback-url/--job-id on the
CLI) and this posts {job_id, ok, image_path|error} to that URL once the run
finishes, so a caller (e.g. linkedin-content-agent's image_service) can spawn
this as a detached subprocess instead of blocking on it. Best-effort only --
a failed callback POST is logged and swallowed, never masks the real
generation result for direct CLI/script callers.
"""
from __future__ import annotations

import logging
from pathlib import Path

from forge2.config import ForgeConfig
from forge2.prompts.templates import build_generate_instruction
from forge2.quality import CorruptOutputError, degenerate_reason
from forge2.schemas import CandidateMeta, CharacterCard, StageManifest, workspace_layout

log = logging.getLogger("forge2.generate")


def _post_callback(callback_url: str, job_id: str | None, ok: bool,
                   image_path: Path | None = None, error: str | None = None) -> None:
    try:
        import requests
        payload = {"job_id": job_id, "ok": ok}
        if ok:
            payload["image_path"] = str(image_path)
        else:
            payload["error"] = error
        requests.post(callback_url, json=payload, timeout=10)
    except Exception:
        log.exception("Callback POST to %s failed (best-effort, ignoring)", callback_url)


def run_generate(cfg: ForgeConfig, character_id: str, task: str,
                 seed: int, profile: str | None = None,
                 out_name: str | None = None,
                 hero_path: Path | None = None,
                 card_path: Path | None = None,
                 output_path: Path | None = None,
                 callback_url: str | None = None,
                 job_id: str | None = None) -> Path:
    try:
        layout = workspace_layout(cfg.workspace_path, character_id)
        resolved_card_path = Path(card_path) if card_path is not None else layout["card"]
        resolved_hero_path = Path(hero_path) if hero_path is not None else layout["hero"]
        if not resolved_card_path.exists():
            raise SystemExit(
                f"character card missing at {resolved_card_path} -- run `forge2 concept` first "
                "or pass --card-path."
            )
        if not resolved_hero_path.exists():
            raise SystemExit(
                f"hero image missing at {resolved_hero_path} -- run `forge2 pick-hero` first "
                "or pass --hero-path."
            )
        if output_path is not None and out_name is not None:
            raise ValueError("pass only one of output_path or out_name")

        card = CharacterCard.load(resolved_card_path)
        if output_path is not None:
            out_path = Path(output_path)
            out_dir = out_path.parent
            fname = out_path.name
        else:
            out_dir = layout["generated"]
            fname = out_name or f"gen_{seed:05d}.png"
        out_dir.mkdir(parents=True, exist_ok=True)

        instruction = build_generate_instruction(card, task)
        log.info("Instruction: %s", instruction)

        from forge2 import backend
        be = backend.get_edit(cfg, profile=profile)
        if not backend.resolve_profile(cfg, profile).negative_prompt_applies:
            log.info("CFG %.1f: ComfyUI ignores the negative prompt for this "
                     "profile; only the positive instruction applies", be.effective_cfg)
        try:
            img = be.edit(image_path=resolved_hero_path, instruction=instruction,
                          negative=cfg.gen.negative_prompt, seed=seed)
        finally:
            be.close()

        img.save(out_dir / fname)
        # Saved first on purpose: the blank file stays on disk for diagnosis.
        reason = degenerate_reason(img)
        if reason:
            raise CorruptOutputError(f"corrupt_output: {reason}; saved as {fname}")
        CandidateMeta(filename=fname, kind="generated", character_id=character_id,
                     seed=seed, prompt=instruction, source_image=str(resolved_hero_path),
                     model_id=be.model_name, steps=be.effective_steps,
                     guidance=be.effective_cfg).save(out_dir)
        manifest_path = out_dir / "manifest.json"
        manifest = StageManifest(stage="generate", character_id=character_id,
                                 config_snapshot={"task": task, "seed": seed,
                                                  "profile": profile})
        manifest.items.append(fname)
        manifest.finish(manifest_path)
        log.info("Saved %s", out_dir / fname)
        out_path = out_dir / fname
    except (Exception, SystemExit) as e:
        # SystemExit (raised by comfy_backend.py's connectivity check and the
        # hero.png-missing guard above) is a BaseException, not an Exception --
        # without catching it explicitly here, a "ComfyUI unreachable" failure
        # exits silently and the caller's callback never fires. Verified via a
        # live test: pointing at an unreachable ComfyUI port produced exit
        # code 1 with zero callback POST until this fix.
        if callback_url:
            _post_callback(callback_url, job_id, ok=False, error=str(e))
        raise

    if callback_url:
        _post_callback(callback_url, job_id, ok=True, image_path=out_path)
    return out_path
