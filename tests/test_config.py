from pathlib import Path

import pytest
from pydantic import ValidationError

from forge2.config import ForgeConfig, load_config


def test_load_config_missing_path_returns_defaults(tmp_path):
    cfg = load_config(tmp_path / "does_not_exist.yaml")
    assert cfg == ForgeConfig()


def test_load_config_reads_yaml_overrides(tmp_path):
    p = tmp_path / "custom.yaml"
    p.write_text(
        "workspace: ./my_workspace\n"
        "comfy:\n"
        "  url: http://example.local:1234\n"
        "  comfy_models_dir: /some/models/dir\n"
        "gen:\n"
        "  speed_profile: lightning\n"
    )
    cfg = load_config(p)
    assert cfg.workspace == "./my_workspace"
    assert cfg.comfy.url == "http://example.local:1234"
    assert cfg.comfy.comfy_models_dir == "/some/models/dir"
    assert cfg.gen.speed_profile == "lightning"
    # untouched keys keep their defaults
    assert cfg.concept.num_candidates == 12


def test_default_config_has_no_hardcoded_personal_path():
    """Regression guard: configs/default.yaml must not bake in a
    machine-specific comfy_models_dir (it broke the config for anyone
    else who cloned the repo -- see git history)."""
    cfg = load_config(Path(__file__).resolve().parents[1] / "configs" / "default.yaml")
    assert cfg.comfy.comfy_models_dir is None


def test_workspace_path_expands_and_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = ForgeConfig(workspace="./workspace")
    assert cfg.workspace_path == (tmp_path / "workspace").resolve()


@pytest.mark.parametrize("profile", ["full", "lightning"])
def test_gen_speed_profile_accepts_known_values(profile):
    cfg = ForgeConfig.model_validate({"gen": {"speed_profile": profile}})
    assert cfg.gen.speed_profile == profile


def test_gen_speed_profile_rejects_unknown_value():
    with pytest.raises(ValidationError):
        ForgeConfig.model_validate({"gen": {"speed_profile": "turbo"}})


MULTI_CHARACTER_NEGATIVES = ("two people", "multiple characters",
                             "duplicate character", "twins", "crowd")


def test_default_negative_prompt_rules_out_a_second_character():
    negative = ForgeConfig().gen.negative_prompt
    for phrase in MULTI_CHARACTER_NEGATIVES:
        assert phrase in negative


def test_default_yaml_negative_prompt_rules_out_a_second_character():
    cfg = load_config(Path(__file__).resolve().parents[1] / "configs" / "default.yaml")
    for phrase in MULTI_CHARACTER_NEGATIVES:
        assert phrase in cfg.gen.negative_prompt
