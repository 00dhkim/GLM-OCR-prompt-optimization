# GLM-OCR Prompt Optimization

PRD-driven implementation for optimizing GLM-OCR prompts on Korean receipt OCR.

## Quick start

```bash
uv sync
uv run glm-ocr-opt --help
```

## Prepare KORIE OCR manifests

```bash
uv run glm-ocr-opt prepare-korie-ocr \
  --train-dir data/korie-ocr/train/train \
  --val-dir data/korie-ocr/val/val \
  --test-dir data/korie-ocr/test/test \
  --output-dir data/manifests/korie-ocr
```

## Expected dataset manifest

The runner accepts JSONL manifests with this shape per line:

```json
{
  "id": "sample-001",
  "image_path": "data/images/sample-001.png",
  "reference_text": "..."
}
```

## Core commands

```bash
uv run glm-ocr-opt seed-eval --manifest data/dev.jsonl --output-dir runs/seed
uv run glm-ocr-opt optimize --manifest data/dev.jsonl --output-dir runs/dev-opt
uv run glm-ocr-opt validate --manifest data/val.jsonl --prompt-file runs/dev-opt/final_prompt.txt --output-dir runs/val
```
