from __future__ import annotations

from PIL import Image

from glm_ocr_prompt_optimization.ocr_client import OCRClient


def test_prepare_image_pads_ultra_wide_line_before_resize() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")
    image = Image.new("RGB", (3200, 48), "white")

    prepared = client._prepare_image(image, max_dimension=1600)

    assert prepared.size == (1600, 96)


def test_prepare_image_leaves_regular_image_without_padding() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")
    image = Image.new("RGB", (800, 1000), "white")

    prepared = client._prepare_image(image, max_dimension=1600)

    assert prepared.size == (800, 1000)


def test_should_chunk_line_image_detects_ultra_wide_lines() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")

    assert client._should_chunk_line_image(Image.new("RGB", (12000, 48), "white")) is True
    assert client._should_chunk_line_image(Image.new("RGB", (3000, 120), "white")) is False


def test_merge_text_segments_uses_overlap() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")

    merged = client._merge_text_segments(["안녕하세요 반갑습니다", "반갑습니다 오늘"])

    assert merged == "안녕하세요 반갑습니다 오늘"
