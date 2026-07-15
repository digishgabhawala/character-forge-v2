"""Download all required model files into ComfyUI's model folders.

Total ~34 GB (Q4 quants). Downloads are resumable (huggingface_hub).
Optional files (lightning LoRAs) are skipped with a warning if the
filename has drifted on the repo -- the pipeline runs fine without them
using speed_profile: full.

Usage:
    forge2 download                          # uses comfy.comfy_models_dir
    forge2 download --comfy-dir ~/ComfyUI/models
    python scripts/download_models.py --comfy-dir ~/ComfyUI/models
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _fetch(hf, target_dir: Path) -> Path | None:
    from huggingface_hub import hf_hub_download
    dest_dir = target_dir / hf.dest
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / hf.local_name
    if final.exists():
        print(f"  already present: {final.name} "
              f"({final.stat().st_size/2**30:.1f} GB)")
        return final
    print(f"  downloading {hf.repo} :: {hf.filename}")
    try:
        got = Path(hf_hub_download(repo_id=hf.repo, filename=hf.filename,
                                   local_dir=dest_dir))
    except Exception as e:
        if hf.optional:
            print(f"  optional file failed ({type(e).__name__}) -- "
                  f"check filename on https://huggingface.co/{hf.repo} ; "
                  f"skipping (use speed_profile: full)")
            return None
        raise
    if got.name != hf.local_name or got.parent != dest_dir:
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(got), final)
        # clean nested dirs hf may create for path-like filenames
        sub = dest_dir / Path(hf.filename).parts[0]
        if sub.is_dir() and sub != dest_dir:
            shutil.rmtree(sub, ignore_errors=True)
    print(f"  done: {final.name} ({final.stat().st_size/2**30:.1f} GB)")
    return final


def run_download(cfg, comfy_dir: str | None = None) -> None:
    target = comfy_dir or cfg.comfy.comfy_models_dir
    if not target:
        sys.exit("Set comfy.comfy_models_dir in the config (path to "
                 "ComfyUI/models) or pass --comfy-dir.")
    target_dir = Path(target).expanduser()
    print(f"Downloading into {target_dir}\n(resumable; ~34 GB total; get "
          f"coffee)\n")
    f = cfg.comfy.files
    for hf in (f.unet_t2i, f.unet_edit, f.clip, f.clip_mmproj, f.vae,
               f.lightning_t2i, f.lightning_edit):
        _fetch(hf, target_dir)
    print("\nDone. Restart ComfyUI so it re-scans the model folders.")


if __name__ == "__main__":
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from forge2.config import load_config
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--comfy-dir", default=None)
    a = ap.parse_args()
    run_download(load_config(a.config), a.comfy_dir)
