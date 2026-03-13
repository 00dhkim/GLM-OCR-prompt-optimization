from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from openai import OpenAI

from .models import AggregateEvaluation, EvaluationResult, PromptCandidate


OPTIMIZER_SYSTEM_PROMPT = """You are optimizing a prompt for Korean receipt OCR.
Return strict JSON with a top-level key named "candidates".
Each candidate must contain "name", "text", and "rationale".
Keep prompts concise and focused on transcription rules.
"""


@dataclass(slots=True)
class FailureExample:
    sample_id: str
    reference_text: str
    predicted_text: str
    cer: float
    non_korean_penalty: float
    repetition_penalty: float
    empty_penalty: float


class PromptOptimizer:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate_candidates(
        self,
        *,
        current_prompt: PromptCandidate,
        aggregate: AggregateEvaluation,
        failures: list[EvaluationResult],
        count: int = 5,
    ) -> list[PromptCandidate]:
        failure_payload = [
            asdict(
                FailureExample(
                    sample_id=row.sample_id,
                    reference_text=row.reference_text,
                    predicted_text=row.predicted_text,
                    cer=row.cer,
                    non_korean_penalty=row.penalties.non_korean_mixed,
                    repetition_penalty=row.penalties.repetition,
                    empty_penalty=row.penalties.empty_or_garbage,
                )
            )
            for row in failures[:15]
        ]
        prompt = {
            "task": "Improve the OCR prompt while preserving plain text OCR output.",
            "constraints": [
                "Do not ask for JSON output.",
                "Focus on transcription rules only.",
                "Discourage Chinese substitution, repetitions, and guessing.",
                f"Return exactly {count} candidates.",
            ],
            "current_prompt": current_prompt.text,
            "aggregate_metrics": asdict(aggregate),
            "failure_examples": failure_payload,
        }

        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "minimal"},
            input=[
                {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        )

        content = response.output_text.strip()
        payload = json.loads(content)
        candidates = []
        for index, item in enumerate(payload["candidates"], start=1):
            candidates.append(
                PromptCandidate(
                    name=item.get("name", f"R{index}"),
                    text=item["text"].strip(),
                    rationale=item.get("rationale", "").strip(),
                )
            )
        return candidates
