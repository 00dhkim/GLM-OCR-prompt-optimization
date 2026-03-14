from __future__ import annotations

import json
import os
import random
import urllib.parse
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


def build_hf_image_text_manifest(
    *,
    dataset_id: str,
    output_dir: Path,
    split: str = "train",
    config: str = "default",
    count: int = 20,
    batch_size: int = 20,
    image_field: str,
    text_field: str,
    sample_prefix: str,
) -> list[DatasetItem]:
    rows = _fetch_hf_rows(
        dataset_id=dataset_id,
        config=config,
        split=split,
        count=count,
        batch_size=batch_size,
    )
    items: list[DatasetItem] = []
    image_dir = output_dir / "images" / split
    image_dir.mkdir(parents=True, exist_ok=True)

    for index, row in enumerate(rows, start=1):
        row_data = row["row"]
        image_payload = row_data[image_field]
        reference_text = row_data[text_field].strip()
        if not reference_text:
            continue

        extension = _infer_extension_from_url(image_payload["src"])
        sample_id = f"{sample_prefix}_{index:04d}"
        local_image = image_dir / f"{sample_id}{extension}"
        _download_file(image_payload["src"], local_image)
        items.append(
            DatasetItem(
                sample_id=sample_id,
                image_path=local_image,
                reference_text=reference_text,
                split=split,
                metadata={
                    "source": dataset_id,
                    "hf_config": config,
                    "hf_split": split,
                    "image_field": image_field,
                    "text_field": text_field,
                },
            )
        )

    _write_manifest(output_dir / f"{split}.jsonl", items)
    return items


def download_hf_repo_image_sample(
    *,
    dataset_id: str,
    output_dir: Path,
    limit: int = 20,
) -> list[Path]:
    repo_info = json.loads(_http_get_text(f"https://huggingface.co/api/datasets/{dataset_id}"))
    candidates = []
    for sibling in repo_info.get("siblings", []):
        filename = sibling.get("rfilename", "")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        candidates.append(filename)

    selected = sorted(candidates)[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for filename in selected:
        local_path = output_dir / Path(filename).name
        remote_url = (
            f"https://huggingface.co/datasets/{dataset_id}/resolve/main/"
            f"{urllib.parse.quote(filename, safe='/')}"
        )
        _download_file(remote_url, local_path)
        downloaded.append(local_path)
    return downloaded


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


def _fetch_hf_rows(
    *,
    dataset_id: str,
    config: str,
    split: str,
    count: int,
    batch_size: int,
) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while len(items) < count:
        chunk = min(batch_size, count - len(items))
        url = (
            "https://datasets-server.huggingface.co/rows?"
            f"dataset={urllib.parse.quote(dataset_id, safe='')}"
            f"&config={urllib.parse.quote(config, safe='')}"
            f"&split={urllib.parse.quote(split, safe='')}"
            f"&offset={offset}&length={chunk}"
        )
        payload = json.loads(_http_get_text(url))
        rows = payload.get("rows", [])
        if not rows:
            break
        items.extend(rows)
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


def _infer_extension_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"


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
