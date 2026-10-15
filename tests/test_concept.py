from PIL import Image

from forge2 import backend as backend_module
from forge2.config import ForgeConfig
from forge2.schemas import CandidateMeta, CharacterCard, SignatureAttribute
from forge2.stages.concept import run_hero_candidate


class _FakeBackend:
    model_name = "fake-t2i"
    effective_steps = 8
    effective_cfg = 1.25

    def __init__(self):
        self.kwargs = None
        self.closed = False

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return Image.new("RGB", (32, 32), (20, 80, 140))

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
