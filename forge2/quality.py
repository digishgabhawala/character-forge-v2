"""Output sanity checks for finished renders.

ComfyUI can return a solid-black (or otherwise uniform) image with no error
when the Mac is short on memory or after a long uptime -- see README's Known
issues. Calibrated on every render in workspace/ (2026-10-11): the corrupt
ones measure a max per-channel stddev of exactly 0.00, the darkest genuine
scene 53. A threshold of 2.0 flags blank output without ever touching a
dark-but-real image.
"""
from __future__ import annotations

from PIL import Image, ImageStat

UNIFORM_STDDEV_THRESHOLD = 2.0
# Exit code `forge2 generate` uses for a corrupt render, so callers (e.g.
# task-queue's image worker) can tell it apart from other failures (exit 1)
# without parsing logs.
CORRUPT_EXIT_CODE = 3


class CorruptOutputError(Exception):
    """The render finished but produced a blank/uniform image."""


def degenerate_reason(img: Image.Image) -> str | None:
    thumb = img.convert("RGB")
    thumb.thumbnail((256, 256))
    spread = max(ImageStat.Stat(thumb).stddev)
    if spread < UNIFORM_STDDEV_THRESHOLD:
        return f"near-uniform image (max channel stddev {spread:.2f})"
    return None
