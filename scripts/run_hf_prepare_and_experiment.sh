#!/usr/bin/env bash

set -euo pipefail

DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 [--dry-run] <run-name> <dataset-id> <sample-prefix> [count]"
  exit 1
fi

RUN_NAME="$1"
DATASET_ID="$2"
SAMPLE_PREFIX="$3"
COUNT="${4:-100}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/external/hf/$RUN_NAME"
MANIFEST_DIR="$ROOT_DIR/data/manifests/$RUN_NAME"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

PREPARE_CMD=(
  uv run glm-ocr-opt prepare-hf-image-text
  --dataset-id "$DATASET_ID"
  --output-dir "$DATA_DIR"
  --split train
  --config default
  --count "$COUNT"
  --batch-size "$COUNT"
  --image-field jpg
  --text-field txt
  --sample-prefix "$SAMPLE_PREFIX"
)

SPLIT_CMD=(
  uv run glm-ocr-opt prepare-split
  --source-manifest "$DATA_DIR/train.jsonl"
  --output-dir "$MANIFEST_DIR"
  --dev-count 60
  --val-count 40
  --seed 42
)

RUN_CMD=(
  "$ROOT_DIR/scripts/run_manifest_experiment.sh"
  "$RUN_NAME"
  "$MANIFEST_DIR/dev.jsonl"
  "$MANIFEST_DIR/val.jsonl"
)

echo "[run-hf-prepare] dataset: $DATASET_ID"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[run-hf-prepare] dry run only"
  printf '[run-hf-prepare] prepare command:'
  printf ' %q' "${PREPARE_CMD[@]}"
  printf '\n'
  printf '[run-hf-prepare] split command:'
  printf ' %q' "${SPLIT_CMD[@]}"
  printf '\n'
  printf '[run-hf-prepare] run command:'
  printf ' %q' "${RUN_CMD[@]}"
  printf '\n'
  exit 0
fi

"${PREPARE_CMD[@]}"

echo "[run-hf-prepare] splitting manifests"
"${SPLIT_CMD[@]}"

"${RUN_CMD[@]}"
