from forge2.backend import resolve_profile
from forge2.config import ForgeConfig


def test_resolve_profile_defaults_to_config_speed_profile():
    cfg = ForgeConfig()
    cfg.gen.speed_profile = "lightning"
    profile = resolve_profile(cfg)
    assert profile.name == "lightning"
    assert profile.use_lightning is True
    assert profile.steps == cfg.gen.steps_lightning
    assert profile.cfg == cfg.gen.cfg_lightning


def test_resolve_profile_override_wins_over_config():
    cfg = ForgeConfig()  # default speed_profile is "full"
    profile = resolve_profile(cfg, override="lightning")
    assert profile.name == "lightning"
    assert profile.use_lightning is True


def test_resolve_profile_full_uses_full_steps_and_cfg():
    cfg = ForgeConfig()
    profile = resolve_profile(cfg, override="full")
    assert profile.name == "full"
    assert profile.use_lightning is False
    assert profile.steps == cfg.gen.steps_full
    assert profile.cfg == cfg.gen.cfg_full
