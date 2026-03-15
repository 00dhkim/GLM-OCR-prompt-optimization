from __future__ import annotations

import base64
import io
import time
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI
from PIL import Image


class OCRClient:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=45.0)
        self._model = model

    def recognize_text(self, *, image_path: Path, prompt: str) -> str:
        text, _ = self.recognize_text_with_timing(image_path=image_path, prompt=prompt)
        return text

    def recognize_text_with_timing(self, *, image_path: Path, prompt: str) -> tuple[str, dict[str, float | int | str]]:
        started_at = time.perf_counter()
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            if self._should_chunk_line_image(image):
                text, details = self._recognize_chunked_line(image=image, prompt=prompt)
            else:
                text, details = self._recognize_with_fallback(image=image, prompt=prompt)
        details["total_seconds"] = time.perf_counter() - started_at
        return text, details

    def _encode_image(self, image_path: Path, max_dimension: int = 800) -> tuple[str, str]:
        with Image.open(image_path) as image:
            image = self._prepare_image(image, max_dimension=max_dimension)
            return self._encode_prepared_image(image)

    def _prepare_image(self, image: Image.Image, *, max_dimension: int = 800) -> Image.Image:
        image = image.convert("RGB")

        # Extremely wide line images collapse to unreadable heights when resized directly.
        width, height = image.size
        if height > 0 and width / height > 12 and height < 192:
            target_height = 192
            padded = Image.new("RGB", (width, target_height), "white")
            top = (target_height - height) // 2
            padded.paste(image, (0, top))
            image = padded

        longest = max(image.size)
        if longest > max_dimension:
            scale = max_dimension / longest
            resized = (max(1, int(image.size[0] * scale)), max(1, int(image.size[1] * scale)))
            image = image.resize(resized)
        return image

    def _encode_prepared_image(self, image: Image.Image) -> tuple[str, str]:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return "image/jpeg", encoded

    def _request_text(self, *, prompt: str, mime_type: str, encoded: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                    ],
                }
            ],
        )
        return (response.choices[0].message.content or "").strip()

    def _recognize_with_fallback(self, *, image: Image.Image, prompt: str) -> tuple[str, dict[str, float | int | str]]:
        preprocess_seconds = 0.0
        request_seconds = 0.0
        attempts = 0
        for max_dimension in (800,):
            preprocess_started_at = time.perf_counter()
            prepared = self._prepare_image(image, max_dimension=max_dimension)
            preprocess_seconds += time.perf_counter() - preprocess_started_at
            mime_type, encoded = self._encode_prepared_image(prepared)
            attempts += 1
            try:
                request_started_at = time.perf_counter()
                text = self._request_text(prompt=prompt, mime_type=mime_type, encoded=encoded)
                request_seconds += time.perf_counter() - request_started_at
                return text, {
                    "preprocess_seconds": preprocess_seconds,
                    "request_seconds": request_seconds,
                    "attempt_count": attempts,
                    "status": "ok",
                }
            except (APITimeoutError, APIConnectionError, InternalServerError):
                request_seconds += time.perf_counter() - request_started_at
                continue
        return "", {
            "preprocess_seconds": preprocess_seconds,
            "request_seconds": request_seconds,
            "attempt_count": attempts,
            "status": "empty_after_retries",
        }

    def _should_chunk_line_image(self, image: Image.Image) -> bool:
        width, height = image.size
        return height > 0 and height <= 64 and width / height > 80

    def _recognize_chunked_line(self, *, image: Image.Image, prompt: str) -> tuple[str, dict[str, float | int | str]]:
        preprocess_started_at = time.perf_counter()
        prepared = self._prepare_image(image, max_dimension=max(image.size[0], image.size[1]))
        preprocess_seconds = time.perf_counter() - preprocess_started_at
        segments = self._split_wide_image(prepared)
        outputs: list[str] = []
        request_seconds = 0.0
        attempts = 0
        for segment in segments:
            preprocess_started_at = time.perf_counter()
            segment = self._prepare_image(segment)
            preprocess_seconds += time.perf_counter() - preprocess_started_at
            mime_type, encoded = self._encode_prepared_image(segment)
            attempts += 1
            try:
                request_started_at = time.perf_counter()
                outputs.append(self._request_text(prompt=prompt, mime_type=mime_type, encoded=encoded))
                request_seconds += time.perf_counter() - request_started_at
            except (APITimeoutError, APIConnectionError, InternalServerError):
                request_seconds += time.perf_counter() - request_started_at
                continue
        return self._merge_text_segments(outputs).strip(), {
            "preprocess_seconds": preprocess_seconds,
            "request_seconds": request_seconds,
            "attempt_count": attempts,
            "status": "ok" if outputs else "empty_after_retries",
        }

    def _split_wide_image(self, image: Image.Image, *, max_chunk_width: int = 1400, overlap: int = 160) -> list[Image.Image]:
        width, height = image.size
        if width <= max_chunk_width:
            return [image]

        chunks: list[Image.Image] = []
        start = 0
        step = max_chunk_width - overlap
        while start < width:
            end = min(width, start + max_chunk_width)
            chunks.append(image.crop((start, 0, end, height)))
            if end == width:
                break
            start += step
        return chunks

    def _merge_text_segments(self, segments: list[str]) -> str:
        merged = ""
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            if not merged:
                merged = segment
                continue
            overlap = self._find_text_overlap(merged, segment)
            if overlap:
                merged += segment[overlap:]
            else:
                merged += " " + segment
        return merged

    def _find_text_overlap(self, left: str, right: str, *, min_overlap: int = 3, max_overlap: int = 64) -> int:
        limit = min(len(left), len(right), max_overlap)
        for size in range(limit, min_overlap - 1, -1):
            if left[-size:] == right[:size]:
                return size
        return 0
