from __future__ import annotations

import pytest
from PIL import Image
from httpx import Request
from openai import APITimeoutError, InternalServerError

from glm_ocr_prompt_optimization.ocr_client import OCRClient

pytestmark = pytest.mark.integration


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


def test_prepare_image_downscales_large_document_pages_more_aggressively() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")
    image = Image.new("RGB", (2480, 3488), "white")

    prepared = client._prepare_image(image, max_dimension=1600)

    assert prepared.size == (853, 1200)


def test_should_chunk_line_image_detects_ultra_wide_lines() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")

    assert client._should_chunk_line_image(Image.new("RGB", (12000, 48), "white")) is True
    assert client._should_chunk_line_image(Image.new("RGB", (3000, 120), "white")) is False


def test_merge_text_segments_uses_overlap() -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")

    merged = client._merge_text_segments(["안녕하세요 반갑습니다", "반갑습니다 오늘"])

    assert merged == "안녕하세요 반갑습니다 오늘"


def test_recognize_with_fallback_retries_smaller_dimensions(monkeypatch) -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")
    seen_sizes = []

    def fake_request(*, prompt: str, mime_type: str, encoded: str) -> str:
        size = seen_sizes[-1]
        if size[1] > 1000:
            response = type("Resp", (), {"request": None, "status_code": 500, "headers": {}})()
            raise InternalServerError("boom", response=response, body={})
        return "ok"

    original_prepare = client._prepare_image

    def wrapped_prepare(image: Image.Image, *, max_dimension: int = 1600) -> Image.Image:
        prepared = original_prepare(image, max_dimension=max_dimension)
        seen_sizes.append(prepared.size)
        return prepared

    monkeypatch.setattr(client, "_prepare_image", wrapped_prepare)
    monkeypatch.setattr(client, "_request_text", fake_request)

    result, timing = client._recognize_with_fallback(
        image=Image.new("RGB", (2480, 3488), "white"),
        prompt="Text Recognition:",
    )

    assert result == "ok"
    assert timing["attempt_count"] == 4
    assert seen_sizes[:4] == [(853, 1200), (853, 1200), (728, 1024), (568, 800)]


def test_recognize_with_fallback_retries_after_timeout(monkeypatch) -> None:
    client = OCRClient(base_url="http://localhost:11434/v1", api_key="ollama", model="glm-ocr:latest")
    seen_sizes = []

    def fake_request(*, prompt: str, mime_type: str, encoded: str) -> str:
        size = seen_sizes[-1]
        if size[1] >= 1200:
            raise APITimeoutError(request=Request("POST", "http://localhost:11434/v1/chat/completions"))
        return "ok"

    original_prepare = client._prepare_image

    def wrapped_prepare(image: Image.Image, *, max_dimension: int = 1600) -> Image.Image:
        prepared = original_prepare(image, max_dimension=max_dimension)
        seen_sizes.append(prepared.size)
        return prepared

    monkeypatch.setattr(client, "_prepare_image", wrapped_prepare)
    monkeypatch.setattr(client, "_request_text", fake_request)

    result, timing = client._recognize_with_fallback(
        image=Image.new("RGB", (2480, 3488), "white"),
        prompt="Text Recognition:",
    )

    assert result == "ok"
    assert timing["attempt_count"] == 3
    assert seen_sizes[:3] == [(853, 1200), (853, 1200), (728, 1024)]
