#!/usr/bin/env bash

set -euo pipefail

DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 [--dry-run] <run-name> <dev-manifest> <val-manifest>"
  exit 1
fi

RUN_NAME="$1"
DEV_MANIFEST="$2"
VAL_MANIFEST="$3"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/runs/$RUN_NAME"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

mkdir -p "$RUN_DIR"

echo "[run-vllm-benchmark] run dir: $RUN_DIR"
echo "[run-vllm-benchmark] dev manifest: $DEV_MANIFEST"
echo "[run-vllm-benchmark] val manifest: $VAL_MANIFEST"

CMD=(
  uv run glm-ocr-opt run-all
  --dev-manifest "$DEV_MANIFEST"
  --val-manifest "$VAL_MANIFEST"
  --output-dir "$RUN_DIR"
  --rounds 3
  --candidates-per-round 6
  --candidate-strategy ocr-rules
)

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[run-vllm-benchmark] dry run only"
  printf '[run-vllm-benchmark] command:'
  printf ' %q' "${CMD[@]}"
  printf '\n'
  exit 0
fi

"${CMD[@]}"

echo "[run-vllm-benchmark] done"
