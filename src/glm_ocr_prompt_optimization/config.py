from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "glm-ocr:latest"
DEFAULT_OPTIMIZER_MODEL = "gpt-5-nano"
DEFAULT_PHOENIX_PROJECT = "glm-ocr-prompt-optimization"


@dataclass(slots=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    ollama_base_url: str
    ollama_api_key: str
    ollama_model: str
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
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            ollama_api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            ollama_model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            arize_api_key=arize_api_key,
            arize_space_id=arize_space_id,
            phoenix_api_key=phoenix_api_key,
            phoenix_collector_endpoint=phoenix_endpoint,
            phoenix_base_url=phoenix_base_url,
            phoenix_project_name=os.getenv("PHOENIX_PROJECT_NAME", DEFAULT_PHOENIX_PROJECT),
            phoenix_client_headers=phoenix_headers,
            output_root=Path(os.getenv("OUTPUT_ROOT", "runs")),
        )
