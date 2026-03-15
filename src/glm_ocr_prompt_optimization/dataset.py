from __future__ import annotations

import json
import os
import random
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image

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
                image_path = _resolve_manifest_path(base_dir, payload["image_path"])
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


def build_aihub_public_admin_manifest(
    *,
    source_dir: Path,
    output_path: Path,
    split: str,
    limit: int | None = None,
    seed: int = 42,
) -> list[DatasetItem]:
    images_root = source_dir / "원천데이터"
    labels_root = source_dir / "라벨링데이터"
    if not images_root.exists() or not labels_root.exists():
        raise ValueError(f"Expected 원천데이터 and 라벨링데이터 under {source_dir}")

    items: list[DatasetItem] = []
    for label_path in sorted(labels_root.rglob("*.json")):
        relative_label = label_path.relative_to(labels_root)
        image_path = images_root / relative_label.with_suffix(".jpg")
        if not image_path.exists():
            continue

        payload = json.loads(label_path.read_text(encoding="utf-8"))
        reference_text = _aihub_public_admin_annotations_to_text(payload.get("annotations", []))
        if not reference_text:
            continue

        category_parts = relative_label.parts[:-2]
        category = "/".join(category_parts) if category_parts else "unknown"
        year = relative_label.parts[-2] if len(relative_label.parts) >= 2 else "unknown"
        items.append(
            DatasetItem(
                sample_id=label_path.stem,
                image_path=image_path,
                reference_text=reference_text,
                split=split,
                metadata={
                    "source": "aihub-public-admin-ocr",
                    "category": category,
                    "year": year,
                    "evaluation_mode": "unordered_characters",
                },
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


def merge_manifests(*, manifest_paths: list[Path], output_path: Path | None = None) -> list[DatasetItem]:
    merged: list[DatasetItem] = []
    seen_ids: set[str] = set()
    for manifest_path in manifest_paths:
        for item in load_manifest(manifest_path):
            if item.sample_id in seen_ids:
                continue
            seen_ids.add(item.sample_id)
            merged.append(item)

    merged.sort(key=lambda item: item.sample_id)
    if output_path is not None:
        write_manifest(output_path, merged)
    return merged


def filter_items_for_benchmark(
    items: list[DatasetItem],
    *,
    max_text_length: int | None = None,
    max_image_width: int | None = None,
    max_aspect_ratio: float | None = None,
) -> list[DatasetItem]:
    filtered: list[DatasetItem] = []
    for item in items:
        if max_text_length is not None and len(item.reference_text) > max_text_length:
            continue

        width, height = _image_size(item.image_path)
        aspect_ratio = width / max(height, 1)
        if max_image_width is not None and width > max_image_width:
            continue
        if max_aspect_ratio is not None and aspect_ratio > max_aspect_ratio:
            continue
        filtered.append(item)
    return filtered


def stratified_split_items(
    items: list[DatasetItem],
    *,
    dev_count: int,
    val_count: int,
    seed: int = 42,
) -> tuple[list[DatasetItem], list[DatasetItem]]:
    requested = dev_count + val_count
    if requested > len(items):
        raise ValueError(f"Requested {requested} items but only {len(items)} are available.")

    rng = random.Random(seed)
    buckets: dict[tuple[str, int, int], list[DatasetItem]] = defaultdict(list)
    for item in items:
        buckets[_benchmark_bucket(item)].append(item)

    for bucket_items in buckets.values():
        rng.shuffle(bucket_items)

    dev_items: list[DatasetItem] = []
    val_items: list[DatasetItem] = []

    ordered_buckets = sorted(buckets.values(), key=len, reverse=True)
    while len(dev_items) < dev_count or len(val_items) < val_count:
        progress = False
        for bucket_items in ordered_buckets:
            if not bucket_items:
                continue
            target = dev_items if len(dev_items) < dev_count else val_items
            if target is val_items and len(val_items) >= val_count:
                continue
            target.append(bucket_items.pop())
            progress = True
            if len(dev_items) >= dev_count and len(val_items) >= val_count:
                break
        if not progress:
            break

    remaining = [item for bucket_items in ordered_buckets for item in bucket_items]
    rng.shuffle(remaining)
    while len(dev_items) < dev_count:
        dev_items.append(remaining.pop())
    while len(val_items) < val_count:
        val_items.append(remaining.pop())

    dev_items.sort(key=lambda item: item.sample_id)
    val_items.sort(key=lambda item: item.sample_id)
    return dev_items, val_items


def write_manifest(path: Path, items: list[DatasetItem], *, split: str | None = None) -> None:
    _write_manifest(path, items, split=split)


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


def _aihub_public_admin_annotations_to_text(annotations: list[dict]) -> str:
    boxes: list[dict[str, float | str]] = []
    for annotation in annotations:
        text = str(annotation.get("annotation.text", "")).strip()
        bbox = annotation.get("annotation.bbox")
        if not text or not isinstance(bbox, list) or len(bbox) != 4:
            continue

        x, y, width, height = bbox
        boxes.append(
            {
                "text": text,
                "x1": float(x),
                "y1": float(y),
                "x2": float(x + width),
                "height": float(height),
                "width": float(width),
            }
        )

    if not boxes:
        return ""

    boxes.sort(key=lambda box: (float(box["y1"]), float(box["x1"])))
    lines: list[list[dict[str, float | str]]] = []
    for box in boxes:
        if not lines:
            lines.append([box])
            continue

        current_line = lines[-1]
        avg_y = sum(float(item["y1"]) for item in current_line) / len(current_line)
        avg_height = sum(float(item["height"]) for item in current_line) / len(current_line)
        if abs(float(box["y1"]) - avg_y) <= max(12.0, avg_height * 0.6):
            current_line.append(box)
        else:
            lines.append([box])

    rendered_lines: list[str] = []
    for line in lines:
        ordered = sorted(line, key=lambda item: float(item["x1"]))
        pieces: list[str] = []
        previous_box: dict[str, float | str] | None = None
        for box in ordered:
            if previous_box is not None:
                gap = float(box["x1"]) - float(previous_box["x2"])
                reference_size = min(float(previous_box["height"]), float(box["width"]))
                if gap > max(8.0, reference_size * 0.45):
                    pieces.append(" ")
            pieces.append(str(box["text"]))
            previous_box = box
        line_text = "".join(pieces).strip()
        if line_text:
            rendered_lines.append(line_text)

    return "\n".join(rendered_lines)


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


def _write_manifest(path: Path, items: list[DatasetItem], *, split: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            payload = {
                "id": item.sample_id,
                "image_path": os.path.relpath(item.image_path, path.parent),
                "reference_text": item.reference_text,
                "split": split or item.split,
                "metadata": item.metadata,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _benchmark_bucket(item: DatasetItem) -> tuple[str, int, int]:
    width, height = _image_size(item.image_path)
    aspect_ratio = width / max(height, 1)
    text_bucket = min(len(item.reference_text) // 20, 6)
    aspect_bucket = min(int(aspect_ratio // 5), 6)
    source = item.metadata.get("source", "unknown")
    return source, text_bucket, aspect_bucket


def _resolve_manifest_path(base_dir: Path, image_path_value: str) -> Path:
    candidate = Path(image_path_value)
    if candidate.is_absolute():
        return candidate

    manifest_relative = base_dir / candidate
    if manifest_relative.exists():
        return manifest_relative

    return candidate
