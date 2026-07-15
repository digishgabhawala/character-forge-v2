"""forge2 CLI -- character-forge-v2. Two capabilities, plus a setup helper:

    forge2 download                          # fetch model files (once)
    forge2 concept examples/character_brief.yaml
    forge2 pick-hero gtee_dev hero_1003.png
    forge2 generate gtee_dev "presenting a chart on a whiteboard, office"

Trimmed fork of character-forge/forge/cli.py -- expand/qc/curate/caption/
train/validate are all dropped (LoRA training abandoned; see character-forge's
project memory for why). This is the whole surface area now.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from forge2.config import load_config

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(message)s",
                    datefmt="%H:%M:%S")

app = typer.Typer(add_completion=False, no_args_is_help=True)
CONFIG_OPT = typer.Option("configs/default.yaml", "--config", "-c")
PROFILE_OPT = typer.Option(None, "--profile", "-p",
                           help="full | lightning (overrides config)")


@app.command()
def download(config: str = CONFIG_OPT,
            comfy_dir: Optional[str] = typer.Option(
                None, help="path to ComfyUI/models (overrides config)")):
    """Download all model files into ComfyUI's model folders (~34 GB)."""
    from scripts.download_models import run_download
    run_download(load_config(config), comfy_dir)


@app.command()
def concept(brief: Path, profile: Optional[str] = PROFILE_OPT,
            config: str = CONFIG_OPT):
    """Character brief -> hero candidates."""
    from forge2.stages.concept import run_concept
    run_concept(load_config(config), brief, profile=profile)


@app.command("pick-hero")
def pick_hero(character_id: str, filename: str, config: str = CONFIG_OPT):
    """Lock one hero candidate as the source of truth."""
    from forge2.stages.concept import pick_hero as _pick
    _pick(load_config(config), character_id, filename)


@app.command()
def generate(character_id: str, task: str,
            seed: int = typer.Option(0, "--seed"),
            profile: Optional[str] = PROFILE_OPT,
            out_name: Optional[str] = typer.Option(None, "--out"),
            callback_url: Optional[str] = typer.Option(
                None, "--callback-url",
                help="POST {job_id, ok, image_path|error} here when done."),
            job_id: Optional[str] = typer.Option(
                None, "--job-id", help="Echoed back in the callback payload."),
            config: str = CONFIG_OPT):
    """Production, no LoRA: hero + freeform instruction -> one image."""
    from forge2.stages.generate import run_generate
    run_generate(load_config(config), character_id, task, seed=seed,
                profile=profile, out_name=out_name,
                callback_url=callback_url, job_id=job_id)


if __name__ == "__main__":
    app()
