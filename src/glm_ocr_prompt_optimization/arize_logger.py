from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict

from .models import AggregateEvaluation


class ArizeLogger:
    def __init__(self, *, api_key: str | None, space_id: str | None) -> None:
        self._api_key = api_key
        self._space_id = space_id

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._space_id)

    def log_aggregate(self, aggregate: AggregateEvaluation) -> bool:
        if not self.enabled:
            return False

        request = urllib.request.Request(
            url="https://app.arize.com/api/v1/space/log",
            data=json.dumps(
                {
                    "space_id": self._space_id,
                    "payload": {
                        "experiment": "glm-ocr-prompt-optimization",
                        "aggregate": asdict(aggregate),
                    },
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                return True
        except Exception:
            return False
