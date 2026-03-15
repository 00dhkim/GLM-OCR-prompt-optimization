#!/usr/bin/env bash

set -euo pipefail

DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 [--dry-run] <run-name> <source-manifest> [<source-manifest> ...]"
  exit 1
fi

RUN_NAME="$1"
shift
SOURCE_MANIFESTS=("$@")

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_DIR="$ROOT_DIR/data/manifests/$RUN_NAME"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

CMD=(
  uv run glm-ocr-opt prepare-heldout-benchmark
  --output-dir "$MANIFEST_DIR"
  --dev-count 16
  --val-count 16
  --seed 42
  --max-text-length 120
  --max-image-width 4096
  --max-aspect-ratio 40
)

for manifest in "${SOURCE_MANIFESTS[@]}"; do
  CMD+=(--source-manifest "$manifest")
done

echo "[run-heldout-benchmark] building held-out manifests in $MANIFEST_DIR"

RUN_CMD=(
  "$ROOT_DIR/scripts/run_manifest_experiment.sh"
  "$RUN_NAME"
  "$MANIFEST_DIR/dev.jsonl"
  "$MANIFEST_DIR/val.jsonl"
)

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[run-heldout-benchmark] dry run only"
  printf '[run-heldout-benchmark] prepare command:'
  printf ' %q' "${CMD[@]}"
  printf '\n'
  printf '[run-heldout-benchmark] run command:'
  printf ' %q' "${RUN_CMD[@]}"
  printf '\n'
  exit 0
fi

"${CMD[@]}"

"${RUN_CMD[@]}"
