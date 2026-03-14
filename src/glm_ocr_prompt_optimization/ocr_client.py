from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path

from openai import OpenAI
from PIL import Image


class OCRClient:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    def recognize_text(self, *, image_path: Path, prompt: str) -> str:
        mime_type, encoded = self._encode_image(image_path)
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

    def _encode_image(self, image_path: Path, max_dimension: int = 1600) -> tuple[str, str]:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            width, height = image.size
            longest = max(width, height)
            if longest > max_dimension:
                scale = max_dimension / longest
                resized = (max(1, int(width * scale)), max(1, int(height * scale)))
                image = image.resize(resized)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return "image/jpeg", encoded
