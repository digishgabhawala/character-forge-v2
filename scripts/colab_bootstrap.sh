#!/usr/bin/env bash
# Installs ComfyUI + the ComfyUI-GGUF custom node + this package (forge2) into
# a fresh Linux+CUDA VM (built for Google Colab, but works on any such box),
# then downloads the ~34GB model set. Uses the system Python directly --
# Colab sessions are already disposable, isolated containers, so a separate
# venv adds friction without adding real safety.
#
# This is the single source of truth for "how does forge2 get set up on a
# fresh machine" -- both this repo's own demo notebook and
# linkedin-content-agent's combined pipeline notebook call this script rather
# than duplicating these steps by hand, so a fix here only has to happen once.
#
# Usage:
#   bash scripts/colab_bootstrap.sh [COMFYUI_DIR] [MODELS_DIR]
#
# COMFYUI_DIR defaults to /content/ComfyUI
# MODELS_DIR defaults to $COMFYUI_DIR/models -- pass a Google Drive path
#   (e.g. /content/drive/MyDrive/character-forge-v2-models) to persist the
#   download across sessions instead of re-downloading every time; this
#   script symlinks $COMFYUI_DIR/models to it in that case.
set -euo pipefail

COMFYUI_DIR="${1:-/content/ComfyUI}"
MODELS_DIR="${2:-$COMFYUI_DIR/models}"
FORGE2_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== ComfyUI -> $COMFYUI_DIR =="
if [ ! -d "$COMFYUI_DIR" ]; then
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
fi
pip install -q -r "$COMFYUI_DIR/requirements.txt"

echo "== ComfyUI-GGUF custom node =="
GGUF_DIR="$COMFYUI_DIR/custom_nodes/ComfyUI-GGUF"
if [ ! -d "$GGUF_DIR" ]; then
  git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git "$GGUF_DIR"
fi
pip install -q -r "$GGUF_DIR/requirements.txt"

echo "== forge2 (this package) =="
pip install -q -e "$FORGE2_DIR"

echo "== Model weights (~34 GB, resumable, skips files already present) -> $MODELS_DIR =="
mkdir -p "$MODELS_DIR"
forge2 download --comfy-dir "$MODELS_DIR"

if [ "$MODELS_DIR" != "$COMFYUI_DIR/models" ]; then
  echo "== Pointing $COMFYUI_DIR/models at $MODELS_DIR =="
  rm -rf "$COMFYUI_DIR/models"
  ln -s "$MODELS_DIR" "$COMFYUI_DIR/models"
fi

# Found live on Colab: the standard ~107GB disk was at 90GB used after this
# script's pip installs + a 34GB model download, before anything downstream
# (e.g. an Ollama pull, in linkedin-content-agent's combined notebook) even
# ran. pip's wheel cache is the one big, unconditionally-safe thing to
# reclaim here -- it holds nothing this script or forge2 needs again this
# session (a re-run just re-downloads).
pip cache purge > /dev/null 2>&1 || true

echo "== Done. Start ComfyUI with: python $COMFYUI_DIR/main.py =="
