from __future__ import annotations

import json
import sys
import urllib.request
import uuid

from .models import AggregateEvaluation


class ArizeLogger:
    DEFAULT_MODEL_ID = "glm-ocr-prompt-optimization"

    def __init__(self, *, api_key: str | None, space_id: str | None) -> None:
        self._api_key = api_key
        self._space_id = space_id
        self._last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._space_id)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def log_aggregate(self, aggregate: AggregateEvaluation) -> bool:
        if not self.enabled:
            self._last_error = "Arize logging disabled because ARIZE_API_KEY or ARIZE_SPACE_ID is missing."
            return False

        body = {
            "model_id": self.DEFAULT_MODEL_ID,
            "model_version": aggregate.prompt_name,
            "prediction_id": str(uuid.uuid4()),
            "prediction": {
                "label": {
                    "numeric": aggregate.mean_total_score,
                }
            },
            "features": {
                "prompt_name": aggregate.prompt_name,
                "prompt_text": aggregate.prompt_text,
                "sample_count": aggregate.sample_count,
                "mean_cer": aggregate.mean_cer,
                "mean_base_score": aggregate.mean_base_score,
                "mean_total_score": aggregate.mean_total_score,
                "non_korean_rate": aggregate.non_korean_rate,
                "repetition_rate": aggregate.repetition_rate,
                "empty_rate": aggregate.empty_rate,
            },
            "tags": {
                "source": "glm-ocr-prompt-optimization",
                "record_type": "aggregate_evaluation",
            },
            "environment_params": {
                "production": {},
            },
        }
        request = urllib.request.Request(
            url="https://api.arize.com/v1/log",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": self._api_key,
                "Grpc-Metadata-space_id": self._space_id,
                "Grpc-Metadata-sdk-language": "rest",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                self._last_error = None
                return True
        except Exception as exc:
            self._last_error = str(exc)
            print(f"[arize] aggregate log failed: {self._last_error}", file=sys.stderr)
            return False
