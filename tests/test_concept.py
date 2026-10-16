import pytest
from PIL import Image
from typer.testing import CliRunner

from forge2 import backend as backend_module
from forge2 import cli
from forge2.config import ForgeConfig
from forge2.quality import CORRUPT_EXIT_CODE, CorruptOutputError
from forge2.schemas import CandidateMeta, CharacterCard, SignatureAttribute
from forge2.stages.concept import run_hero_candidate


class _FakeBackend:
    model_name = "fake-t2i"
    effective_steps = 8
    effective_cfg = 1.25

    def __init__(self, blank=False):
        self.kwargs = None
        self.closed = False
        self.blank = blank

    def generate(self, **kwargs):
        self.kwargs = kwargs
        if self.blank:  # what ComfyUI returns under memory pressure
            return Image.new("RGB", (32, 32), (0, 0, 0))
        return Image.linear_gradient("L").resize((32, 32)).convert("RGB")

    def close(self):
        self.closed = True


def test_one_hero_candidate_is_stateless_and_writes_provenance(tmp_path, monkeypatch):
    cfg = ForgeConfig(workspace=str(tmp_path / "unused-workspace"))
    card_path = tmp_path / "input" / "character.json"
    card_path.parent.mkdir()
    CharacterCard(
        character_id="remote-dev",
        trigger_token="remote-dev",
        base_description="an Indian software developer mascot",
        signature_attributes=[
            SignatureAttribute(name="green tee", prompt_phrase="green t-shirt")
        ],
    ).save(card_path)
    output_path = tmp_path / "task" / "candidate.png"
    fake = _FakeBackend()
    selected_profile = []

    def get_t2i(config, profile=None):
        selected_profile.append(profile)
        return fake

    monkeypatch.setattr(backend_module, "get_t2i", get_t2i)

    result = run_hero_candidate(cfg, card_path, seed=1701,
                                output_path=output_path, profile="lightning")

    assert result == output_path and output_path.exists()
    assert selected_profile == ["lightning"]
    assert fake.kwargs["seed"] == 1701
    assert "green t-shirt" in fake.kwargs["prompt"]
    assert fake.closed is True
    meta = CandidateMeta.model_validate_json(
        output_path.with_suffix(".json").read_text())
    assert meta.filename == "candidate.png"
    assert meta.character_id == "remote-dev"
    assert meta.seed == 1701
    assert meta.model_id == "fake-t2i"
    assert not (tmp_path / "unused-workspace" / "remote-dev").exists()


def _card(tmp_path):
    card_path = tmp_path / "input" / "character.json"
    card_path.parent.mkdir(exist_ok=True)
    CharacterCard(character_id="remote-dev", trigger_token="remote-dev",
                  base_description="an Indian software developer mascot").save(card_path)
    return card_path


def test_blank_hero_candidate_is_rejected_not_offered(tmp_path, monkeypatch):
    """A hero becomes the reference for every later post, so a blank one must
    fail like a blank post render does -- never reach the Studio as ready."""
    cfg = ForgeConfig(workspace=str(tmp_path / "unused-workspace"))
    fake = _FakeBackend(blank=True)
    monkeypatch.setattr(backend_module, "get_t2i", lambda config, profile=None: fake)
    output_path = tmp_path / "task" / "candidate.png"

    with pytest.raises(CorruptOutputError, match="^corrupt_output: near-uniform"):
        run_hero_candidate(cfg, _card(tmp_path), seed=7, output_path=output_path)

    assert output_path.exists()  # kept for diagnosis, as for post renders
    assert not output_path.with_suffix(".json").exists()  # no provenance = not a candidate
    assert fake.closed is True


def test_hero_candidate_cli_exits_with_corrupt_code(tmp_path, monkeypatch):
    fake = _FakeBackend(blank=True)
    monkeypatch.setattr(backend_module, "get_t2i", lambda config, profile=None: fake)
    result = CliRunner().invoke(cli.app, [
        "hero-candidate", str(_card(tmp_path)), "--seed", "7",
        "--output-path", str(tmp_path / "out" / "candidate.png")])
    assert result.exit_code == CORRUPT_EXIT_CODE
    assert "corrupt_output:" in result.output
