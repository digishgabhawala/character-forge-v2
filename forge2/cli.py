"""forge2 CLI -- character-forge-v2. Two capabilities, plus a setup helper:

    forge2 download                          # fetch model files (once)
    forge2 concept examples/character_brief.yaml
    forge2 hero-candidate character.json --seed 1000 --output-path hero.png
    forge2 pick-hero gtee_dev hero_1003.png
    forge2 generate gtee_dev "presenting a chart on a whiteboard, office"

Trimmed fork of character-forge/forge/cli.py -- expand/qc/curate/caption/
train/validate are all dropped (LoRA training abandoned; see character-forge's
project memory for why). This is the whole surface area now.
"""
from __future__ import annotations

import logging
from pathlib import Path

import typer

from forge2.config import load_config

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(message)s",
                    datefmt="%H:%M:%S")

app = typer.Typer(add_completion=False, no_args_is_help=True)
CONFIG_OPT = typer.Option("configs/default.yaml", "--config", "-c")
PROFILE_OPT = typer.Option(None, "--profile", "-p",
                           help="full | lightning (overrides config)")
HERO_PATH_OPT = typer.Option(
    None, "--hero-path",
    help="Explicit locked hero image; defaults to workspace/<id>/hero.png.")
CARD_PATH_OPT = typer.Option(
    None, "--card-path",
    help="Explicit character card; defaults to workspace/<id>/character.json.")
OUTPUT_PATH_OPT = typer.Option(
    None, "--output-path",
    help="Explicit output file, useful for stateless/temporary workers.")
HERO_OUTPUT_PATH_OPT = typer.Option(
    ..., "--output-path",
    help="Required output file for this stateless hero candidate.")


@app.command()
def download(config: str = CONFIG_OPT,
            comfy_dir: str | None = typer.Option(
                None, help="path to ComfyUI/models (overrides config)")):
    """Download all model files into ComfyUI's model folders (~34 GB)."""
    from scripts.download_models import run_download
    run_download(load_config(config), comfy_dir)


@app.command()
def concept(brief: Path, profile: str | None = PROFILE_OPT,
            config: str = CONFIG_OPT):
    """Character brief -> hero candidates."""
    from forge2.stages.concept import run_concept
    run_concept(load_config(config), brief, profile=profile)


@app.command("hero-candidate")
def hero_candidate(card: Path,
                   seed: int = typer.Option(..., "--seed"),
                   output_path: Path = HERO_OUTPUT_PATH_OPT,
                   profile: str | None = PROFILE_OPT,
                   config: str = CONFIG_OPT):
    """CharacterCard + seed -> one candidate at an explicit output path."""
    from forge2.stages.concept import run_hero_candidate
    run_hero_candidate(load_config(config), card, seed, output_path,
                       profile=profile)


@app.command("pick-hero")
def pick_hero(character_id: str, filename: str, config: str = CONFIG_OPT):
    """Lock one hero candidate as the source of truth."""
    from forge2.stages.concept import pick_hero as _pick
    _pick(load_config(config), character_id, filename)


@app.command()
def generate(character_id: str, task: str,
            seed: int = typer.Option(0, "--seed"),
            profile: str | None = PROFILE_OPT,
            out_name: str | None = typer.Option(None, "--out"),
            hero_path: Path | None = HERO_PATH_OPT,
            card_path: Path | None = CARD_PATH_OPT,
            output_path: Path | None = OUTPUT_PATH_OPT,
            callback_url: str | None = typer.Option(
                None, "--callback-url",
                help="POST {job_id, ok, image_path|error} here when done."),
            job_id: str | None = typer.Option(
                None, "--job-id", help="Echoed back in the callback payload."),
            config: str = CONFIG_OPT):
    """Production, no LoRA: hero + freeform instruction -> one image."""
    from forge2.quality import CORRUPT_EXIT_CODE, CorruptOutputError
    from forge2.stages.generate import run_generate
    try:
        run_generate(load_config(config), character_id, task, seed=seed,
                     profile=profile, out_name=out_name,
                     hero_path=hero_path, card_path=card_path,
                     output_path=output_path,
                     callback_url=callback_url, job_id=job_id)
    except CorruptOutputError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(CORRUPT_EXIT_CODE) from e


if __name__ == "__main__":
    app()
