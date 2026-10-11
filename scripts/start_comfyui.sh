#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_DIR=$(dirname -- "$(dirname -- "$SCRIPT_DIR")")
COMFYUI_DIR=${COMFYUI_DIR:-"$WORKSPACE_DIR/imgworks/ComfyUI"}
COMFYUI_PYTHON=${COMFYUI_PYTHON:-"$WORKSPACE_DIR/comfyui-env/bin/python"}

cd "$COMFYUI_DIR"
exec "$COMFYUI_PYTHON" main.py --cache-none "$@"
