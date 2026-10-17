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

GENERATE_TEMPLATE = (
    "This is {name}, a {style} character. Keep the exact same character with "
    "identical face, hairstyle, body proportions, outfit and colors "
    "({identity}). Change only the following: {task}. Solo: a single "
    "character, only one person in the image -- never a second copy of "
    "{name}. Same art style, clean bold linework, flat colors."
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
    )
