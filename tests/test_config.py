from __future__ import annotations

from glm_ocr_prompt_optimization.config import Settings


def test_settings_load_prefers_ocr_variables(monkeypatch) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.setenv("OCR_API_KEY", "EMPTY")
    monkeypatch.setenv("OCR_MODEL", "GLM-OCR")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "glm-ocr:latest")

    settings = Settings.load()

    assert settings.ocr_base_url == "http://localhost:8000/v1"
    assert settings.ocr_api_key == "EMPTY"
    assert settings.ocr_model == "GLM-OCR"


def test_settings_load_falls_back_to_legacy_ollama_variables(monkeypatch) -> None:
    monkeypatch.delenv("OCR_BASE_URL", raising=False)
    monkeypatch.delenv("OCR_API_KEY", raising=False)
    monkeypatch.delenv("OCR_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "glm-ocr:latest")

    settings = Settings.load()

    assert settings.ocr_base_url == "http://localhost:11434/v1"
    assert settings.ocr_api_key == "ollama"
    assert settings.ocr_model == "glm-ocr:latest"
