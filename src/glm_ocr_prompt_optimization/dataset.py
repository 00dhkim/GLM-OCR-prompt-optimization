from __future__ import annotations

import json
import os
import random
from pathlib import Path

from .models import DatasetItem


def load_manifest(path: Path) -> list[DatasetItem]:
    if path.suffix != ".jsonl":
        raise ValueError(f"Unsupported manifest format: {path}")

    base_dir = path.parent
    items: list[DatasetItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            try:
                sample_id = payload["id"]
                image_path = base_dir / payload["image_path"]
                reference_text = payload["reference_text"]
            except KeyError as exc:
                raise ValueError(f"Manifest parse error at line {line_number}: missing {exc}") from exc

            metadata = payload.get("metadata", {})
            items.append(
                DatasetItem(
                    sample_id=sample_id,
                    image_path=image_path,
                    reference_text=reference_text,
                    split=payload.get("split"),
                    metadata=metadata,
                )
            )

    return items


def build_korie_ocr_manifest(
    *,
    source_dir: Path,
    output_path: Path,
    split: str,
    limit: int | None = None,
    seed: int = 42,
) -> list[DatasetItem]:
    image_paths = sorted(
        path for path in source_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    items: list[DatasetItem] = []

    for image_path in image_paths:
        label_path = image_path.with_suffix(".txt")
        if not label_path.exists():
            continue
        sample_id = image_path.stem
        category = sample_id.split("_", 1)[1] if "_" in sample_id else "unknown"
        reference_text = label_path.read_text(encoding="utf-8").strip()
        items.append(
            DatasetItem(
                sample_id=sample_id,
                image_path=image_path,
                reference_text=reference_text,
                split=split,
                metadata={"category": category},
            )
        )

    if limit is not None and len(items) > limit:
        rng = random.Random(seed)
        items = rng.sample(items, limit)
        items.sort(key=lambda item: item.sample_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in items:
            payload = {
                "id": item.sample_id,
                "image_path": os.path.relpath(item.image_path, output_path.parent),
                "reference_text": item.reference_text,
                "split": item.split,
                "metadata": item.metadata,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return items
