from __future__ import annotations

import os
from typing import Any, Callable, Sequence

import pandas as pd
from openai.types.chat.completion_create_params import CompletionCreateParamsBase

from .models import AggregateEvaluation, PromptCandidate


class ArizeLogger:
    PROMPT_NAME = "glm-ocr-transcription"

    def __init__(
        self,
        *,
        api_key: str | None,
        space_id: str | None,
        endpoint: str | None = None,
        base_url: str | None = None,
        project_name: str = "glm-ocr-prompt-optimization",
        client_headers: str | None = None,
        model_name: str = "glm-ocr:latest",
    ) -> None:
        self._api_key = api_key
        self._space_id = space_id
        self._endpoint = endpoint
        self._base_url = base_url
        self._project_name = project_name
        self._client_headers = client_headers or self._build_headers(api_key=api_key, space_id=space_id)
        self._model_name = model_name
        self._client = None
        self._instrumented = False
        self._last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._space_id)

    @property
    def supports_experiments(self) -> bool:
        return bool(self._base_url and self._api_key)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def create_dataset(
        self,
        *,
        name: str,
        dataframe: pd.DataFrame,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        metadata_keys: Sequence[str] = (),
        split_keys: Sequence[str] = (),
        description: str | None = None,
    ) -> Any | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            return client.datasets.create_dataset(
                name=name,
                dataframe=dataframe,
                input_keys=input_keys,
                output_keys=output_keys,
                metadata_keys=metadata_keys,
                split_keys=split_keys,
                dataset_description=description,
            )
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def create_prompt_version(
        self,
        *,
        prompt: PromptCandidate,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            params = CompletionCreateParamsBase(
                model=self._model_name,
                temperature=0,
                messages=[
                    {"role": "system", "content": prompt.text},
                    {"role": "user", "content": "{{image_path}}"},
                ],
            )
            from phoenix.client.types import PromptVersion

            version = PromptVersion.from_openai(params, model_provider="OLLAMA")
            return client.prompts.create(
                name=self.PROMPT_NAME,
                prompt_description=description,
                prompt_metadata=metadata,
                version=version,
            )
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def run_experiment(
        self,
        *,
        dataset: Any,
        task: Callable[..., Any],
        evaluators: Sequence[Callable[..., Any]] | None,
        experiment_name: str,
        experiment_description: str,
        experiment_metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        if not self.supports_experiments or dataset is None:
            return None
        self.ensure_instrumentation()
        try:
            from phoenix.experiments import run_experiment

            return run_experiment(
                dataset,
                task=task,
                evaluators=list(evaluators or []),
                experiment_name=experiment_name,
                experiment_description=experiment_description,
                experiment_metadata=experiment_metadata,
                print_summary=False,
            )
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def ensure_instrumentation(self) -> None:
        if not self.enabled or self._instrumented:
            return
        os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = self._endpoint or ""
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from arize.otel import register

        register_kwargs = {
            "space_id": self._space_id or "",
            "api_key": self._api_key or "",
            "project_name": self._project_name,
            "verbose": False,
            "log_to_console": False,
        }
        if self._endpoint:
            register_kwargs["endpoint"] = self._endpoint
        tracer_provider = register(**register_kwargs)
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        self._instrumented = True

    def log_aggregate(self, aggregate: AggregateEvaluation) -> bool:
        self.ensure_instrumentation()
        self._last_error = None if self.enabled else "Arize AX integration is disabled."
        return self.enabled

    def log_prompt_learning_round(self, row: Any) -> bool:
        self.ensure_instrumentation()
        self._last_error = None if self.enabled else "Arize AX integration is disabled."
        return self.enabled

    def log_prompt_candidate(self, *, round_index: int, candidate: PromptCandidate, aggregate: AggregateEvaluation) -> bool:
        self.ensure_instrumentation()
        self._last_error = None if self.enabled else "Arize AX integration is disabled."
        return self.enabled

    def _get_client(self) -> Any | None:
        if not self.supports_experiments:
            self._last_error = "Phoenix client integration disabled because PHOENIX_BASE_URL or API key is missing."
            return None
        if self._client is not None:
            return self._client
        try:
            from phoenix.client import Client

            self._client = Client(
                base_url=self._base_url,
                api_key=self._api_key,
                headers=self._extra_headers(),
            )
            self._last_error = None
            return self._client
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def _build_headers(self, *, api_key: str | None, space_id: str | None) -> str | None:
        if not api_key:
            return None
        header = f"api_key={api_key}"
        if space_id:
            header = f"{header},space_id={space_id}"
        return header

    def _headers_dict(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        if not self._client_headers:
            return pairs
        for item in self._client_headers.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            pairs[key.strip()] = value.strip()
        return pairs

    def _extra_headers(self) -> dict[str, str]:
        headers = self._headers_dict()
        headers.pop("api_key", None)
        return headers
