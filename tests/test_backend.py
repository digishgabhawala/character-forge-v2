import io

from PIL import Image

from forge2.backend import resolve_profile
from forge2.comfy_backend import ComfyBackend
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


def test_negative_prompt_is_ignored_at_cfg_one():
    """ComfyUI's sampling_function drops the negative (uncond) branch when
    cfg == 1.0, so the lightning profile never sees gen.negative_prompt."""
    cfg = ForgeConfig()
    assert resolve_profile(cfg, override="lightning").negative_prompt_applies is False
    assert resolve_profile(cfg, override="full").negative_prompt_applies is True


def test_completed_comfy_job_frees_models(monkeypatch):
    png = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(png, format="PNG")
    free_calls = []

    class Response:
        def __init__(self, payload=None, content=b"", status_code=200):
            self.payload = payload
            self.content = content
            self.status_code = status_code
            self.text = ""

        def json(self):
            return self.payload

        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        if url.endswith("/prompt"):
            return Response({"prompt_id": "p1"})
        free_calls.append((url, json))
        return Response({})

    def fake_get(url, **kwargs):
        if "/history/" in url:
            return Response({
                "p1": {
                    "status": {"status_str": "success"},
                    "outputs": {"9": {"images": [{"filename": "out.png"}]}},
                }
            })
        return Response(content=png.getvalue())

    monkeypatch.setattr("forge2.comfy_backend.requests.post", fake_post)
    monkeypatch.setattr("forge2.comfy_backend.requests.get", fake_get)

    backend = ComfyBackend.__new__(ComfyBackend)
    backend.url = "http://127.0.0.1:8188"
    backend.client_id = "client"
    backend.cfg = type("Cfg", (), {"comfy": type("Comfy", (), {
        "timeout_s": 5, "poll_s": 0,
    })()})()

    result = backend._submit_and_fetch({"1": {}})

    assert result.size == (2, 2)
    assert free_calls == [(
        "http://127.0.0.1:8188/free",
        {"unload_models": True, "free_memory": True},
    )]
