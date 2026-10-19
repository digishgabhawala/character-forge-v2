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


def test_build_generate_instruction_leads_with_the_single_character_constraint():
    """Lightning renders run at CFG 1.0, where ComfyUI never evaluates the
    negative prompt, so the positive instruction alone must carry the solo
    constraint -- first, before the identity lock and the scene."""
    instruction = build_generate_instruction(_card(), "presenting a chart to a team")
    opening = instruction.lower()[:160]
    assert opening.startswith("exactly one character")
    assert "only one person" in opening
    assert "no second copy of dev" in opening
    assert "reflection" in opening
    assert instruction.index("Exactly one character") < instruction.index("This is Dev")
    assert instruction.index("This is Dev") < instruction.index("presenting a chart to a team")


def test_build_generate_instruction_repeats_the_solo_constraint_after_the_scene():
    instruction = build_generate_instruction(_card(), "waving")
    after_task = instruction.split("waving", 1)[1].lower()
    assert "only one person" in after_task


def test_build_generate_instruction_carries_no_logo_no_text_constraints_early():
    """Lightning (CFG 1.0) ignores the negative prompt, and two of three
    lightning renders drew an Apple logo on the laptop. The no-logo / no-text
    constraints must be in the positive instruction, before the scene."""
    instruction = build_generate_instruction(_card(), "typing on a laptop")
    lowered = instruction.lower()
    before_task = lowered.split("typing on a laptop", 1)[0]
    assert "plain unbranded" in before_task
    assert "no brand logos" in before_task
    assert "trademarks" in before_task
    assert "no readable text" in before_task
    assert "letters" in before_task
    assert "never photorealistic" in before_task


def test_build_generate_instruction_includes_card_negative_traits():
    card = _card()
    card.negative_traits = "no hats, never wearing a tie"
    instruction = build_generate_instruction(card, "waving")
    assert "no hats, never wearing a tie" in instruction


def test_build_generate_instruction_without_negative_traits_has_no_dangling_label():
    instruction = build_generate_instruction(_card(), "waving")
    assert "Also: ." not in instruction
    assert "  " not in instruction


def test_build_generate_instruction_constraint_preamble_stays_concise():
    """Everything before the identity lock should stay short so the scene
    and identity still dominate the prompt."""
    instruction = build_generate_instruction(_card(), "waving")
    preamble = instruction.split("This is Dev", 1)[0]
    assert len(preamble) < 450


def test_default_negative_prompt_still_lists_logos_and_text():
    from forge2.config import load_config
    neg = load_config().gen.negative_prompt.lower()
    for term in ("brand logos", "trademarks", "text", "letters", "photorealistic"):
        assert term in neg
