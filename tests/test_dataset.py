from pathlib import Path

from glm_ocr_prompt_optimization.dataset import build_korie_ocr_manifest, load_manifest


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
