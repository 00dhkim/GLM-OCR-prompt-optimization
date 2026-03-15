#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-quick}"

run_cli_check() {
  echo "[codex-preflight] checking CLI help"
  uv run glm-ocr-opt --help >/dev/null
}

run_quick_tests() {
  echo "[codex-preflight] running quick unit tests"
  uv run pytest -q -m unit
}

run_integration_tests() {
  echo "[codex-preflight] running integration tests"
  uv run pytest -q -m integration
}

run_full_tests() {
  echo "[codex-preflight] running full test suite"
  uv run pytest -q
}

case "$MODE" in
  quick)
    run_quick_tests
    ;;
  --cli)
    run_quick_tests
    run_integration_tests
    run_cli_check
    ;;
  --full)
    run_full_tests
    ;;
  *)
    echo "Usage: $0 [--cli|--full]"
    exit 1
    ;;
esac
