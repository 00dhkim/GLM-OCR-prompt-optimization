from __future__ import annotations

import json
import os
import random
import urllib.request
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


def build_cord_v2_manifest(
    *,
    output_dir: Path,
    train_count: int = 60,
    validation_count: int = 100,
    batch_size: int = 20,
) -> tuple[list[DatasetItem], list[DatasetItem]]:
    train_items = _fetch_cord_split(
        split="train",
        count=train_count,
        batch_size=batch_size,
        output_dir=output_dir,
    )
    validation_items = _fetch_cord_split(
        split="validation",
        count=validation_count,
        batch_size=batch_size,
        output_dir=output_dir,
    )
    _write_manifest(output_dir / "dev.jsonl", train_items)
    _write_manifest(output_dir / "val.jsonl", validation_items)
    return train_items, validation_items


def _fetch_cord_split(
    *,
    split: str,
    count: int,
    batch_size: int,
    output_dir: Path,
) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    if split == "train" and count <= 26:
        payload = json.loads(
            _http_get_text(
                "https://datasets-server.huggingface.co/first-rows?"
                "dataset=naver-clova-ix%2Fcord-v2&config=default&split=train"
            )
        )
        return _cord_rows_to_items(rows=payload["rows"][:count], split=split, output_dir=output_dir)

    offset = 0
    while len(items) < count:
        chunk = min(batch_size, count - len(items))
        url = (
            "https://datasets-server.huggingface.co/rows?"
            f"dataset=naver-clova-ix%2Fcord-v2&config=default&split={split}&offset={offset}&length={chunk}"
        )
        payload = json.loads(_http_get_text(url))
        items.extend(_cord_rows_to_items(rows=payload["rows"], split=split, output_dir=output_dir))
        offset += chunk
    return items[:count]


def _cord_rows_to_items(*, rows: list[dict], split: str, output_dir: Path) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    for row in rows:
        row_data = row["row"]
        ground_truth = json.loads(row_data["ground_truth"])
        image_url = row_data["image"]["src"]
        image_id = ground_truth["meta"]["image_id"]
        local_image = output_dir / "images" / split / f"{image_id:04d}.jpg"
        local_image.parent.mkdir(parents=True, exist_ok=True)
        _download_file(image_url, local_image)
        reference_text = _cord_ground_truth_to_text(ground_truth)
        items.append(
            DatasetItem(
                sample_id=f"CORD_{split}_{image_id:04d}",
                image_path=local_image,
                reference_text=reference_text,
                split="dev" if split == "train" else "val",
                metadata={"source": "cord-v2", "hf_split": split},
            )
        )
    return items


def _cord_ground_truth_to_text(ground_truth: dict) -> str:
    valid_lines = ground_truth.get("valid_line", [])
    ordered_lines = []
    for line in valid_lines:
        words = line.get("words", [])
        if not words:
            continue
        sorted_words = sorted(words, key=_cord_word_position)
        line_text = " ".join(word["text"].strip() for word in sorted_words if word.get("text", "").strip())
        if not line_text:
            continue
        y_positions = [word["quad"]["y1"] for word in sorted_words]
        x_positions = [word["quad"]["x1"] for word in sorted_words]
        ordered_lines.append((sum(y_positions) / len(y_positions), sum(x_positions) / len(x_positions), line_text))
    ordered_lines.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(line[2] for line in ordered_lines)


def _cord_word_position(word: dict) -> tuple[float, float]:
    quad = word["quad"]
    x = (quad["x1"] + quad["x2"] + quad["x3"] + quad["x4"]) / 4
    y = (quad["y1"] + quad["y2"] + quad["y3"] + quad["y4"]) / 4
    return y, x


def _http_get_text(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def _download_file(url: str, path: Path) -> None:
    if path.exists():
        return
    with urllib.request.urlopen(url) as response:
        path.write_bytes(response.read())


def _write_manifest(path: Path, items: list[DatasetItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            payload = {
                "id": item.sample_id,
                "image_path": os.path.relpath(item.image_path, path.parent),
                "reference_text": item.reference_text,
                "split": item.split,
                "metadata": item.metadata,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
