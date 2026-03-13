from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "glm-ocr:latest"
DEFAULT_OPTIMIZER_MODEL = "gpt-5-nano"


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

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", DEFAULT_OPTIMIZER_MODEL),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            ollama_api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            ollama_model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            arize_api_key=os.getenv("ARIZE_API_KEY"),
            arize_space_id=os.getenv("ARIZE_SPACE_ID"),
            output_root=Path(os.getenv("OUTPUT_ROOT", "runs")),
        )
