
from forge2.schemas import (
    CharacterCard,
    SignatureAttribute,
    ensure_dirs,
    workspace_layout,
)


def _card(**overrides) -> CharacterCard:
    defaults = {
        "character_id": "test_char",
        "trigger_token": "test_char",
        "base_description": "a friendly cartoon character",
        "signature_attributes": [
            SignatureAttribute(name="green t-shirt", prompt_phrase="plain solid green t-shirt"),
            SignatureAttribute(name="round glasses", prompt_phrase="large round black-rimmed glasses"),
        ],
    }
    defaults.update(overrides)
    return CharacterCard(**defaults)


def test_identity_phrase_combines_description_and_attributes():
    phrase = _card().identity_phrase()
    assert "a friendly cartoon character" in phrase
    assert "plain solid green t-shirt" in phrase
    assert "large round black-rimmed glasses" in phrase


def test_identity_phrase_skips_empty_pieces():
    card = _card(base_description="", signature_attributes=[])
    assert card.identity_phrase() == ""


def test_character_card_save_load_roundtrip(tmp_path):
    card = _card()
    path = tmp_path / "character.json"
    card.save(path)

    loaded = CharacterCard.load(path)
    assert loaded == card


def test_workspace_layout_paths(tmp_path):
    layout = workspace_layout(tmp_path, "gtee_dev")
    assert layout["base"] == tmp_path / "gtee_dev"
    assert layout["card"] == tmp_path / "gtee_dev" / "character.json"
    assert layout["hero"] == tmp_path / "gtee_dev" / "hero.png"
    assert layout["hero_candidates"] == tmp_path / "gtee_dev" / "01_hero_candidates"
    assert layout["generated"] == tmp_path / "gtee_dev" / "generated"


def test_ensure_dirs_creates_directories_but_not_files(tmp_path):
    layout = workspace_layout(tmp_path, "gtee_dev")
    ensure_dirs(layout)

    assert layout["hero_candidates"].is_dir()
    assert layout["generated"].is_dir()
    # "card" and "hero" are files, not dirs -- must not be created as dirs
    assert not layout["card"].exists()
    assert not layout["hero"].exists()
