from pathlib import Path

from glm_ocr_prompt_optimization.dataset import (
    _cord_ground_truth_to_text,
    _infer_extension_from_url,
    build_korie_ocr_manifest,
    load_manifest,
)


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
