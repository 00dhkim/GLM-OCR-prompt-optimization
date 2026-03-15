from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_OCR_BASE_URL = "http://localhost:8000/v1"
DEFAULT_OCR_API_KEY = "EMPTY"
DEFAULT_OCR_MODEL = "GLM-OCR"
DEFAULT_OPTIMIZER_MODEL = "gpt-5-nano"
DEFAULT_PHOENIX_PROJECT = "glm-ocr-prompt-optimization"


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
    phoenix_api_key: str | None = None
    phoenix_collector_endpoint: str | None = None
    phoenix_base_url: str | None = None
    phoenix_project_name: str = DEFAULT_PHOENIX_PROJECT
    phoenix_client_headers: str | None = None

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        arize_api_key = os.getenv("ARIZE_API_KEY")
        arize_space_id = os.getenv("ARIZE_SPACE_ID")
        phoenix_api_key = os.getenv("PHOENIX_API_KEY", arize_api_key)
        phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        phoenix_base_url = os.getenv("PHOENIX_BASE_URL")
        phoenix_headers = os.getenv("PHOENIX_CLIENT_HEADERS")
        if not phoenix_headers and phoenix_api_key:
            phoenix_headers = f"api_key={phoenix_api_key}"
            if arize_space_id:
                phoenix_headers = f"{phoenix_headers},space_id={arize_space_id}"
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", DEFAULT_OPTIMIZER_MODEL),
            ocr_base_url=_first_env("OCR_BASE_URL", "OLLAMA_BASE_URL", default=DEFAULT_OCR_BASE_URL) or DEFAULT_OCR_BASE_URL,
            ocr_api_key=_first_env("OCR_API_KEY", "OLLAMA_API_KEY", default=DEFAULT_OCR_API_KEY) or DEFAULT_OCR_API_KEY,
            ocr_model=_first_env("OCR_MODEL", "OLLAMA_MODEL", default=DEFAULT_OCR_MODEL) or DEFAULT_OCR_MODEL,
            arize_api_key=arize_api_key,
            arize_space_id=arize_space_id,
            phoenix_api_key=phoenix_api_key,
            phoenix_collector_endpoint=phoenix_endpoint,
            phoenix_base_url=phoenix_base_url,
            phoenix_project_name=os.getenv("PHOENIX_PROJECT_NAME", DEFAULT_PHOENIX_PROJECT),
            phoenix_client_headers=phoenix_headers,
            output_root=Path(os.getenv("OUTPUT_ROOT", "runs")),
        )
