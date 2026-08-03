"""Blocks until a ComfyUI server responds at /system_stats, or exits non-zero
after a timeout.

Exists for notebook use (Colab or plain Jupyter): a notebook cell can't
"leave a terminal open" the way local usage does (see README's "Every time
you want to use this" section) -- ComfyUI has to be started as a background
process from one cell, then polled from the next before any forge2 command
can talk to it. Both this repo's own demo notebook and
linkedin-content-agent's combined pipeline notebook use this.

Usage: python scripts/wait_for_comfyui.py [url] [timeout_seconds]
"""
from __future__ import annotations

import sys
import time

import requests


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8188"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    url = f"{base_url}/system_stats"

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(url, timeout=5).status_code == 200:
                print("ComfyUI is up.")
                return 0
        except requests.RequestException:
            pass
        time.sleep(3)

    print(f"ComfyUI did not respond at {url} within {timeout}s.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
