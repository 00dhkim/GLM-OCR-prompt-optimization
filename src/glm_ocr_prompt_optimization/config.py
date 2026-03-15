from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_OCR_BASE_URL = "http://localhost:8000/v1"
DEFAULT_OCR_API_KEY = "EMPTY"
DEFAULT_OCR_MODEL = "GLM-OCR"
DEFAULT_OPTIMIZER_MODEL = "gpt-5-nano"


def _first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


@dataclass(slots=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    ocr_base_url: str
    ocr_api_key: str
    ocr_model: str
    arize_api_key: str | None
    arize_space_id: str | None
    output_root: Path

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", DEFAULT_OPTIMIZER_MODEL),
            ocr_base_url=_first_env("OCR_BASE_URL", "OLLAMA_BASE_URL", default=DEFAULT_OCR_BASE_URL) or DEFAULT_OCR_BASE_URL,
            ocr_api_key=_first_env("OCR_API_KEY", "OLLAMA_API_KEY", default=DEFAULT_OCR_API_KEY) or DEFAULT_OCR_API_KEY,
            ocr_model=_first_env("OCR_MODEL", "OLLAMA_MODEL", default=DEFAULT_OCR_MODEL) or DEFAULT_OCR_MODEL,
            arize_api_key=os.getenv("ARIZE_API_KEY"),
            arize_space_id=os.getenv("ARIZE_SPACE_ID"),
            output_root=Path(os.getenv("OUTPUT_ROOT", "runs")),
        )
