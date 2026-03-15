from __future__ import annotations

import pytest

from glm_ocr_prompt_optimization.arize_logger import ArizeLogger
from glm_ocr_prompt_optimization.models import AggregateEvaluation, PromptCandidate

pytestmark = pytest.mark.integration


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
        chinese_rate=0.1,
        repetition_rate=0.0,
    )


def test_create_dataset_uses_phoenix_client(monkeypatch) -> None:
    seen = {}

    class FakeDatasets:
        def create_dataset(self, **kwargs):
            seen.update(kwargs)
            return {"id": "dataset-1"}

    class FakeClient:
        datasets = FakeDatasets()

    logger = ArizeLogger(
        api_key="key",
        space_id="space",
        endpoint="https://app.phoenix.arize.com",
        base_url="https://app.phoenix.arize.com/s/my-space",
        client_headers="api_key=key,space_id=space",
    )
    monkeypatch.setattr(logger, "_get_client", lambda: FakeClient())

    result = logger.create_dataset(
        name="ocr-dev",
        dataframe=None,  # type: ignore[arg-type]
        input_keys=["image_path"],
        output_keys=["reference_text"],
        metadata_keys=["metadata_json"],
        split_keys=["split"],
        description="dataset",
    )

    assert result == {"id": "dataset-1"}
    assert seen["name"] == "ocr-dev"
    assert seen["input_keys"] == ["image_path"]
    assert seen["output_keys"] == ["reference_text"]


def test_log_methods_are_compatibility_noops_when_enabled() -> None:
    logger = ArizeLogger(
        api_key="key",
        space_id="space",
        endpoint="https://app.phoenix.arize.com",
        base_url="https://app.phoenix.arize.com/s/my-space",
        client_headers="api_key=key,space_id=space",
    )

    assert logger.log_aggregate(_sample_aggregate()) is True
    assert logger.log_prompt_candidate(
        round_index=1,
        candidate=PromptCandidate(name="P1", text="Text Recognition:"),
        aggregate=_sample_aggregate(),
    ) is True


def test_disabled_logger_records_error() -> None:
    logger = ArizeLogger(api_key=None, space_id=None)

    assert logger.create_dataset(
        name="disabled",
        dataframe=None,  # type: ignore[arg-type]
        input_keys=[],
        output_keys=[],
    ) is None
    assert logger.last_error is not None


def test_get_client_uses_base_url_and_bearer_api_key(monkeypatch) -> None:
    seen = {}

    class FakeClient:
        def __init__(self, *, base_url=None, api_key=None, headers=None):
            seen["base_url"] = base_url
            seen["api_key"] = api_key
            seen["headers"] = headers

    monkeypatch.setattr("phoenix.client.Client", FakeClient)

    logger = ArizeLogger(
        api_key="key",
        space_id="space",
        endpoint="https://app.phoenix.arize.com",
        base_url="https://app.phoenix.arize.com/s/my-space",
        client_headers="api_key=key,space_id=space",
    )

    logger._get_client()

    assert seen["base_url"] == "https://app.phoenix.arize.com/s/my-space"
    assert seen["api_key"] == "key"
    assert seen["headers"] == {"space_id": "space"}
