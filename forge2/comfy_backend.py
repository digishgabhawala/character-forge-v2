"""ComfyUI headless backend.

Talks to a locally running ComfyUI server over HTTP. You never open the
node-graph GUI: this module loads a workflow template JSON (API format),
rewrites its inputs, submits it, polls history, and pulls the image back.

Robustness rules:
  * Nodes are located by class_type (and _meta.title for positive/negative),
    NOT by hardcoded ids -- so you can replace our templates with a fresh
    export from your own ComfyUI ("Export (API)") and things keep working
    as long as the positive/negative encode nodes keep their titles.
  * Text fields are set on whichever of ("text", "prompt") the node exposes.
  * The lightning speed-profile LoRA is INJECTED into the model chain at
    runtime -- templates stay LoRA-free.

Unchanged from character-forge/forge/comfy_backend.py except: import path
(forge2), and the character-LoRA injection path is removed (v2 has no
training path, so there is never a trained character LoRA to inject).
"""
from __future__ import annotations

import copy
import io
import json
import logging
import time
import uuid
from pathlib import Path

import requests
from PIL import Image

from forge2.backend import Profile

log = logging.getLogger("forge2.comfy")

TEXT_ENCODE_CLASSES = ("CLIPTextEncode", "TextEncodeQwenImageEdit",
                       "TextEncodeQwenImageEditPlus")


# ---------------------------------------------------------------------------
# Graph helpers (pure functions -- unit-testable without a server)
# ---------------------------------------------------------------------------

def find_nodes(graph: dict, class_type: str) -> list[str]:
    return [nid for nid, n in graph.items()
            if n.get("class_type") == class_type]


def find_one(graph: dict, class_type: str) -> str:
    ids = find_nodes(graph, class_type)
    if not ids:
        raise KeyError(f"workflow has no node of class {class_type}")
    return ids[0]


def find_by_title(graph: dict, title: str) -> str | None:
    for nid, n in graph.items():
        if n.get("_meta", {}).get("title", "").lower() == title.lower():
            return nid
    return None


def set_text(graph: dict, node_id: str, value: str) -> None:
    inputs = graph[node_id]["inputs"]
    for key in ("text", "prompt"):
        if key in inputs:
            inputs[key] = value
            return
    raise KeyError(f"node {node_id} has no text/prompt input")


def set_prompts(graph: dict, positive: str, negative: str) -> None:
    pos = find_by_title(graph, "positive")
    neg = find_by_title(graph, "negative")
    if pos is None or neg is None:  # fallback: first/second encode node
        enc = [nid for c in TEXT_ENCODE_CLASSES for nid in find_nodes(graph, c)]
        enc.sort(key=int)
        if len(enc) < 2:
            raise KeyError("could not locate positive/negative encode nodes")
        pos = pos or enc[0]
        neg = neg or enc[1]
    set_text(graph, pos, positive)
    set_text(graph, neg, negative)


def inject_lora(graph: dict, lora_name: str, strength: float) -> None:
    """Insert LoraLoaderModelOnly between the model source and the sampling
    chain (ModelSamplingAuraFlow if present, else KSampler)."""
    try:
        target = find_one(graph, "ModelSamplingAuraFlow")
    except KeyError:
        target = find_one(graph, "KSampler")
    src = graph[target]["inputs"]["model"]           # [node_id, output_idx]
    new_id = f"lora_{len(find_nodes(graph, 'LoraLoaderModelOnly')) + 1}_inj"
    graph[new_id] = {
        "class_type": "LoraLoaderModelOnly",
        "_meta": {"title": f"lora:{lora_name}"},
        "inputs": {"lora_name": lora_name, "strength_model": strength,
                   "model": src},
    }
    graph[target]["inputs"]["model"] = [new_id, 0]


def configure_common(graph: dict, cfg, profile: Profile, kind: str,
                     seed: int) -> None:
    files = cfg.comfy.files
    # loaders
    graph[find_one(graph, "UnetLoaderGGUF")]["inputs"]["unet_name"] = (
        files.unet_t2i.local_name if kind == "t2i"
        else files.unet_edit.local_name)
    for nid in find_nodes(graph, "CLIPLoaderGGUF"):
        graph[nid]["inputs"]["clip_name"] = files.clip.local_name
    for nid in find_nodes(graph, "VAELoader"):
        graph[nid]["inputs"]["vae_name"] = files.vae.local_name
    # sampling
    for nid in find_nodes(graph, "ModelSamplingAuraFlow"):
        graph[nid]["inputs"]["shift"] = cfg.comfy.shift
    ks = graph[find_one(graph, "KSampler")]["inputs"]
    ks.update(seed=seed, steps=profile.steps, cfg=profile.cfg,
              sampler_name=cfg.comfy.sampler, scheduler=cfg.comfy.scheduler,
              denoise=1.0)


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class ComfyBackend:
    def __init__(self, cfg, kind: str, profile: Profile):
        self.cfg = cfg
        self.kind = kind
        self.profile = profile
        self.url = cfg.comfy.url.rstrip("/")
        self.client_id = uuid.uuid4().hex
        tmpl = (cfg.comfy.workflow_t2i if kind == "t2i"
                else cfg.comfy.workflow_edit)
        self.template = json.loads(Path(tmpl).read_text())
        self.effective_steps = profile.steps
        self.effective_cfg = profile.cfg
        files = cfg.comfy.files
        self.model_name = (files.unet_t2i.local_name if kind == "t2i"
                           else files.unet_edit.local_name)
        self._ping()

    # -- server io -----------------------------------------------------
    def _ping(self) -> None:
        try:
            requests.get(f"{self.url}/system_stats", timeout=5).raise_for_status()
        except Exception as e:
            raise SystemExit(
                f"Cannot reach ComfyUI at {self.url} ({e}).\n"
                f"Start it first:  cd ~/ComfyUI && python main.py") from e

    def _upload(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            r = requests.post(f"{self.url}/upload/image",
                              files={"image": (image_path.name, f, "image/png")},
                              data={"overwrite": "true"}, timeout=120)
        r.raise_for_status()
        return r.json()["name"]

    def _submit_and_fetch(self, graph: dict) -> Image.Image:
        r = requests.post(f"{self.url}/prompt",
                          json={"prompt": graph, "client_id": self.client_id},
                          timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"ComfyUI rejected workflow: {r.text[:2000]}")
        pid = r.json()["prompt_id"]

        deadline = time.time() + self.cfg.comfy.timeout_s
        while time.time() < deadline:
            h = requests.get(f"{self.url}/history/{pid}", timeout=30).json()
            if pid in h:
                entry = h[pid]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(
                        f"ComfyUI execution error: "
                        f"{json.dumps(status)[:2000]}")
                for node_out in entry.get("outputs", {}).values():
                    for im in node_out.get("images", []):
                        raw = requests.get(
                            f"{self.url}/view",
                            params={"filename": im["filename"],
                                    "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")},
                            timeout=120).content
                        return Image.open(io.BytesIO(raw)).convert("RGB")
            time.sleep(self.cfg.comfy.poll_s)
        raise TimeoutError(
            f"Image not ready after {self.cfg.comfy.timeout_s}s -- raise "
            f"comfy.timeout_s (Mac + 20B + full steps can be slow).")

    # -- graph assembly --------------------------------------------------
    def _lightning_name(self) -> str | None:
        f = self.cfg.comfy.files
        hf = f.lightning_t2i if self.kind == "t2i" else f.lightning_edit
        return hf.local_name if hf else None

    def _build(self, seed: int) -> dict:
        g = copy.deepcopy(self.template)
        configure_common(g, self.cfg, self.profile, self.kind, seed)
        if self.profile.use_lightning:
            name = self._lightning_name()
            if name:
                inject_lora(g, name, 1.0)
            else:
                log.warning("lightning profile but no lightning LoRA "
                            "configured; running at lightning steps anyway "
                            "(quality will suffer)")
        return g

    # -- public api -------------------------------------------------------
    def generate(self, *, prompt: str, negative: str, seed: int,
                 width: int, height: int) -> Image.Image:
        g = self._build(seed)
        set_prompts(g, prompt, negative)
        lat = graph_latent = find_one(g, "EmptySD3LatentImage")
        g[graph_latent]["inputs"].update(width=width, height=height,
                                         batch_size=1)
        _ = lat
        return self._submit_and_fetch(g)

    def edit(self, *, image_path: Path, instruction: str, negative: str,
             seed: int) -> Image.Image:
        g = self._build(seed)
        uploaded = self._upload(image_path)
        for nid in find_nodes(g, "LoadImage"):
            g[nid]["inputs"]["image"] = uploaded
        set_prompts(g, instruction, negative)
        return self._submit_and_fetch(g)

    def close(self) -> None:
        # ComfyUI manages its own model memory (loads/unloads between the
        # t2i and edit UNets automatically). Nothing to free client-side.
        pass
