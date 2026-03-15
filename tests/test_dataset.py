import json
from pathlib import Path

import pytest

from glm_ocr_prompt_optimization.dataset import (
    _cord_ground_truth_to_text,
    _infer_extension_from_url,
    _resolve_manifest_path,
    build_korie_ocr_manifest,
    filter_items_for_benchmark,
    load_manifest,
    merge_manifests,
    stratified_split_items,
)

pytestmark = pytest.mark.unit


def test_load_manifest_reads_jsonl(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    image = tmp_path / "sample.png"
    image.write_bytes(b"fake")
    manifest.write_text(
        '{"id":"s1","image_path":"sample.png","reference_text":"abc","split":"dev","metadata":{"lang":"ko"}}\n',
        encoding="utf-8",
    )

    items = load_manifest(manifest)

    assert len(items) == 1
    assert items[0].sample_id == "s1"
    assert items[0].image_path == image
    assert items[0].reference_text == "abc"
    assert items[0].split == "dev"
    assert items[0].metadata == {"lang": "ko"}


def test_build_korie_ocr_manifest_creates_jsonl(tmp_path: Path) -> None:
    source_dir = tmp_path / "train"
    source_dir.mkdir()
    (source_dir / "IMG00001_Total.jpg").write_bytes(b"fake")
    (source_dir / "IMG00001_Total.txt").write_text("12,000", encoding="utf-8")

    output_path = tmp_path / "manifests" / "dev.jsonl"
    items = build_korie_ocr_manifest(
        source_dir=source_dir,
        output_path=output_path,
        split="dev",
        limit=None,
    )

    assert len(items) == 1
    assert output_path.exists()
    loaded = load_manifest(output_path)
    assert loaded[0].sample_id == "IMG00001_Total"
    assert loaded[0].reference_text == "12,000"
    assert loaded[0].metadata == {"category": "Total"}


def test_cord_ground_truth_to_text_sorts_by_line_and_word_position() -> None:
    ground_truth = {
        "valid_line": [
            {
                "words": [
                    {"text": "World", "quad": {"x1": 50, "x2": 60, "x3": 60, "x4": 50, "y1": 10, "y2": 10, "y3": 20, "y4": 20}},
                    {"text": "Hello", "quad": {"x1": 10, "x2": 20, "x3": 20, "x4": 10, "y1": 10, "y2": 10, "y3": 20, "y4": 20}},
                ]
            },
            {
                "words": [
                    {"text": "123", "quad": {"x1": 10, "x2": 20, "x3": 20, "x4": 10, "y1": 40, "y2": 40, "y3": 50, "y4": 50}}
                ]
            },
        ]
    }

    text = _cord_ground_truth_to_text(ground_truth)

    assert text == "Hello World\n123"


def test_infer_extension_from_url_uses_known_suffix() -> None:
    assert _infer_extension_from_url("https://example.com/a/b/sample.png?x=1") == ".png"
    assert _infer_extension_from_url("https://example.com/no-extension") == ".jpg"


def test_infer_extension_from_url_handles_encoded_filename() -> None:
    assert _infer_extension_from_url("https://example.com/a%20b/sample.JPEG") == ".jpeg"


def test_resolve_manifest_path_falls_back_to_repo_relative_path(tmp_path: Path) -> None:
    repo_relative = tmp_path / "external" / "sample.jpg"
    repo_relative.parent.mkdir(parents=True)
    repo_relative.write_bytes(b"fake")

    resolved = _resolve_manifest_path(tmp_path / "manifests", str(repo_relative.relative_to(tmp_path)))

    assert resolved == repo_relative.relative_to(tmp_path)


def test_merge_manifests_deduplicates_by_sample_id(tmp_path: Path) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"fake")
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(
        '{"id":"s1","image_path":"sample.png","reference_text":"abc","split":"dev","metadata":{}}\n',
        encoding="utf-8",
    )
    second.write_text(
        '{"id":"s1","image_path":"sample.png","reference_text":"abc","split":"val","metadata":{}}\n'
        '{"id":"s2","image_path":"sample.png","reference_text":"def","split":"val","metadata":{}}\n',
        encoding="utf-8",
    )

    merged = merge_manifests(manifest_paths=[first, second])

    assert [item.sample_id for item in merged] == ["s1", "s2"]


def test_filter_items_for_benchmark_respects_limits(tmp_path: Path) -> None:
    short = tmp_path / "short.png"
    short.write_bytes(b"fake")
    long = tmp_path / "long.png"
    long.write_bytes(b"fake")

    from PIL import Image

    Image.new("RGB", (1200, 80), "white").save(short)
    Image.new("RGB", (6000, 48), "white").save(long)

    items = load_manifest(
        _write_manifest(
            tmp_path / "source.jsonl",
            [
                {"id": "s1", "image_path": "short.png", "reference_text": "짧은 문장", "split": "train", "metadata": {}},
                {
                    "id": "s2",
                    "image_path": "long.png",
                    "reference_text": "긴 문장" * 50,
                    "split": "train",
                    "metadata": {},
                },
            ],
        )
    )

    filtered = filter_items_for_benchmark(
        items,
        max_text_length=20,
        max_image_width=2000,
        max_aspect_ratio=40,
    )

    assert [item.sample_id for item in filtered] == ["s1"]


def test_stratified_split_items_returns_requested_counts(tmp_path: Path) -> None:
    from PIL import Image

    manifest = tmp_path / "source.jsonl"
    rows = []
    for index in range(12):
        image_path = tmp_path / f"sample_{index}.png"
        width = 1200 if index < 6 else 1600
        height = 80
        Image.new("RGB", (width, height), "white").save(image_path)
        rows.append(
            {
                "id": f"s{index:02d}",
                "image_path": image_path.name,
                "reference_text": "짧은 문장" if index % 2 == 0 else "조금 더 긴 문장입니다",
                "split": "train",
                "metadata": {"source": "test"},
            }
        )
    items = load_manifest(_write_manifest(manifest, rows))

    dev_items, val_items = stratified_split_items(items, dev_count=4, val_count=4, seed=7)

    assert len(dev_items) == 4
    assert len(val_items) == 4
    assert not ({item.sample_id for item in dev_items} & {item.sample_id for item in val_items})


def _write_manifest(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path
