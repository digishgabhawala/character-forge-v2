import random

import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from forge2 import backend as backend_module
from forge2 import cli
from forge2.config import ForgeConfig
from forge2.quality import CORRUPT_EXIT_CODE, CorruptOutputError, degenerate_reason
from forge2.schemas import CharacterCard
from forge2.stages import generate as generate_stage


def test_solid_black_image_is_degenerate():
    assert degenerate_reason(Image.new("RGB", (512, 512), (0, 0, 0)))


def test_uniform_colour_image_is_degenerate():
    assert degenerate_reason(Image.new("RGB", (512, 512), (200, 120, 160)))


def test_dark_image_with_detail_is_not_degenerate():
    # A night scene: mostly near-black, but with a dim gradient and a lit
    # object -- real dark renders measured >= 53 max channel stddev.
    img = Image.new("RGB", (512, 512))
    draw = ImageDraw.Draw(img)
    for x in range(512):
        draw.line([(x, 0), (x, 511)], fill=(x * 40 // 512, x * 40 // 512, x * 50 // 512))
    draw.rectangle([200, 300, 320, 380], fill=(180, 150, 90))
    assert degenerate_reason(img) is None


def test_noisy_image_is_not_degenerate():
    rng = random.Random(0)
    img = Image.new("RGB", (64, 64))
    img.putdata([tuple(rng.randrange(256) for _ in range(3)) for _ in range(64 * 64)])
    assert degenerate_reason(img) is None


class _BlackBackend:
    model_name = "fake"
    effective_steps = 1
    effective_cfg = 1.0

    def edit(self, **kwargs):
        return Image.new("RGB", (64, 64), (0, 0, 0))

    def close(self):
        pass


def test_corrupt_render_fails_and_reports_callback(tmp_path, monkeypatch):
    cfg = ForgeConfig(workspace=str(tmp_path))
    base = tmp_path / "dev"
    base.mkdir()
    CharacterCard(character_id="dev", trigger_token="dev").save(base / "character.json")
    Image.new("RGB", (64, 64), (255, 255, 255)).save(base / "hero.png")
    monkeypatch.setattr(backend_module, "get_edit", lambda cfg, profile=None: _BlackBackend())
    callbacks = []
    monkeypatch.setattr(generate_stage, "_post_callback",
                        lambda url, job_id, ok, **kw: callbacks.append((ok, kw)))

    with pytest.raises(CorruptOutputError, match=r"^corrupt_output:"):
        generate_stage.run_generate(cfg, "dev", "waving", seed=7, out_name="out.png",
                                    callback_url="http://cb", job_id="j1")

    assert (base / "generated" / "out.png").exists()  # kept for diagnosis
    assert callbacks[0][0] is False
    assert callbacks[0][1]["error"].startswith("corrupt_output:")


def test_cli_exits_with_corrupt_code(monkeypatch):
    def boom(*args, **kwargs):
        raise CorruptOutputError("corrupt_output: near-uniform image")

    monkeypatch.setattr(generate_stage, "run_generate", boom)
    result = CliRunner().invoke(cli.app, ["generate", "dev", "waving"])
    assert result.exit_code == CORRUPT_EXIT_CODE
    assert "corrupt_output:" in result.output
