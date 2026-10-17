from forge2.prompts.templates import build_generate_instruction, build_hero_prompt
from forge2.schemas import CharacterCard, SignatureAttribute


def _card() -> CharacterCard:
    return CharacterCard(
        character_id="gtee_dev",
        trigger_token="gtee_dev",
        display_name="Dev",
        style_tag="flat vector cartoon mascot, thick outlines",
        base_description="a friendly male software engineer cartoon character",
        signature_attributes=[
            SignatureAttribute(name="green t-shirt", prompt_phrase="plain solid green t-shirt"),
        ],
    )


def test_build_hero_prompt_includes_style_and_identity():
    prompt = build_hero_prompt(_card())
    assert "flat vector cartoon mascot, thick outlines" in prompt
    assert "a friendly male software engineer cartoon character" in prompt
    assert "plain solid green t-shirt" in prompt


def test_build_generate_instruction_includes_task_and_identity_lock():
    instruction = build_generate_instruction(_card(), "presenting a chart on a whiteboard")
    assert "presenting a chart on a whiteboard" in instruction
    assert "Dev" in instruction
    assert "plain solid green t-shirt" in instruction
    assert "Keep the exact same character" in instruction


def test_build_generate_instruction_falls_back_to_character_id_without_display_name():
    card = _card()
    card.display_name = ""
    instruction = build_generate_instruction(card, "waving")
    assert "This is gtee_dev" in instruction


def test_build_generate_instruction_asks_for_exactly_one_character():
    """Some production renders came back with a second copy of the mascot;
    the instruction must ask for exactly one character."""
    instruction = build_generate_instruction(_card(), "presenting a chart to a team")
    lowered = instruction.lower()
    assert "solo" in lowered
    assert "a single character" in lowered
    assert "only one person" in lowered


def test_build_hero_prompt_asks_for_exactly_one_character():
    lowered = build_hero_prompt(_card()).lower()
    assert "solo" in lowered
    assert "a single character" in lowered
    assert "only one person" in lowered
