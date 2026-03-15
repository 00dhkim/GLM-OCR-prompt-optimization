from __future__ import annotations

import json

import pytest

from glm_ocr_prompt_optimization.arize_logger import ArizeLogger
from glm_ocr_prompt_optimization.models import AggregateEvaluation

pytestmark = pytest.mark.integration


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _sample_aggregate() -> AggregateEvaluation:
    return AggregateEvaluation(
        prompt_name="baseline",
        prompt_text="Text Recognition:",
        sample_count=10,
        mean_raw_cer=0.22,
        mean_cer=0.2,
        mean_token_f1=0.85,
        mean_base_score=0.8,
        mean_total_score=0.75,
        non_korean_rate=0.1,
        repetition_rate=0.0,
        empty_rate=0.0,
    )


def test_log_aggregate_uses_arize_ax_endpoint(monkeypatch) -> None:
    logger = ArizeLogger(api_key="key", space_id="space")
    seen = {}

    def fake_urlopen(request, timeout=10):
        seen["url"] = request.full_url
        seen["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert logger.log_aggregate(_sample_aggregate()) is True
    assert seen["url"] == "https://api.arize.com/v1/log"
    assert seen["headers"]["authorization"] == "key"
    assert seen["headers"]["grpc-metadata-space_id"] == "space"
    assert seen["body"]["model_id"] == "glm-ocr-prompt-optimization"
    assert seen["body"]["model_version"] == "baseline"
    assert seen["body"]["prediction"]["label"]["numeric"] == 0.75
    assert seen["body"]["features"]["mean_raw_cer"] == 0.22
    assert seen["body"]["features"]["mean_cer"] == 0.2


def test_log_aggregate_records_error_when_disabled() -> None:
    logger = ArizeLogger(api_key=None, space_id=None)

    assert logger.log_aggregate(_sample_aggregate()) is False
    assert logger.last_error is not None
