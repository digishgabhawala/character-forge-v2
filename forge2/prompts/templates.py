"""Prompt construction. Trimmed fork of character-forge/forge/prompts/templates.py.

The consistency rule encoded here: the IDENTITY chunk (from CharacterCard)
is byte-identical in every prompt. Edit instructions explicitly say what to
PRESERVE before what to CHANGE -- instruction-editors reward this phrasing.

Dropped from v1: EDIT_TEMPLATE/build_edit_instruction (fixed-axis dataset
expansion) and TURNAROUND_TEMPLATE (multi-view sheet generation) -- both
were for building a LoRA training dataset, which v2 no longer does.
"""
from __future__ import annotations

from forge2.schemas import CharacterCard

# ---------------------------------------------------------------------------
# Stage 1: hero generation
# ---------------------------------------------------------------------------

HERO_TEMPLATE = (
    "{style}, solo, a single character, only one person, character design of "
    "{identity}, full body, standing, facing the "
    "viewer, arms relaxed at sides, neutral friendly expression, centered "
    "composition, plain white background, clean bold linework, flat colors, "
    "high quality character reference"
)


def build_hero_prompt(card: CharacterCard) -> str:
    return HERO_TEMPLATE.format(style=card.style_tag,
                                identity=card.identity_phrase())


# ---------------------------------------------------------------------------
# Stage 2: production generation (no-LoRA, reference-conditioned)
# ---------------------------------------------------------------------------

# The solo constraint LEADS the instruction (and is repeated after the
# scene). It cannot live only in gen.negative_prompt: the lightning profile
# samples at CFG 1.0, where ComfyUI skips the negative conditioning entirely
# (comfy/samplers.py sampling_function: cond_scale == 1.0 -> uncond = None),
# so for lightning the positive text is the only thing the model reads. A
# real lightning render of a "collaborative" scene came back with two copies
# of the mascot despite the negative prompt -- see Profile.negative_prompt_applies.
GENERATE_TEMPLATE = (
    "Exactly one character in the image: {name} alone, solo, only one person "
    "-- no second person, no second copy of {name}, no reflection or "
    "duplicate. "
    "{clean} "
    "This is {name}, a {style} character. Keep the exact same character with "
    "identical face, hairstyle, body proportions, outfit and colors "
    "({identity}). Change only the following: {task}. Solo: a single "
    "character, only one person in the image -- never a second copy of "
    "{name}. Same art style, clean bold linework, flat colors.{avoid}"
)

# Same reasoning as the solo constraint: "brand logos" / "text" used to live
# only in gen.negative_prompt, which lightning (CFG 1.0) never reads -- two of
# three lightning renders drew an Apple logo on the laptop. Stated positively
# first ("plain unbranded"), so the model has something to draw instead.
CLEAN_CONSTRAINTS = (
    "Plain unbranded objects: a plain unbranded laptop with a blank lid, plain "
    "devices and plain clothing -- no brand logos or trademarks anywhere, no "
    "readable text, words, letters or numbers. Flat 2D cartoon illustration, "
    "never photorealistic."
)


def build_generate_instruction(card: CharacterCard, task: str) -> str:
    """Production path: freeform scene/action description instead of a
    fixed VariationSpec. Same identity-lock phrasing character-forge v1
    validated in its `expand` stage -- reused per-call instead of pre-baked
    into a training dataset."""
    return GENERATE_TEMPLATE.format(
        name=card.display_name or card.character_id,
        style=card.style_tag,
        identity=card.identity_phrase(),
        task=task,
        clean=CLEAN_CONSTRAINTS,
        avoid=_avoid_clause(card),
    )


def _avoid_clause(card: CharacterCard) -> str:
    """The card's own negative_traits, restated in the positive text (the
    negative prompt does not apply on lightning)."""
    traits = card.negative_traits.strip().rstrip(".")
    return f" Also: {traits}." if traits else ""
