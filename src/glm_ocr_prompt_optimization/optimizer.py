from __future__ import annotations

import json
import unicodedata
from dataclasses import asdict, dataclass

from openai import OpenAI

from .models import AggregateEvaluation, EvaluationResult, PromptCandidate


OPTIMIZER_SYSTEM_PROMPT = """You optimize prompts for plain-text OCR.
Return strict JSON with a top-level key named "candidates".
Each candidate must contain "name", "text", and "rationale".
Prefer concise prompts written in English.
The prompt is for transcription only, not extraction or JSON formatting.
Strong candidates usually:
- say to transcribe only visible text
- require plain text output only
- forbid translation, correction, normalization, and guessing
- preserve reading order and line breaks when visually clear
- forbid repeated text
"""

FALLBACK_CANDIDATES = [
    PromptCandidate(
        name="ENG-F1",
        text=(
            "Text Recognition:\n"
            "Transcribe all visible text exactly as it appears.\n"
            "Output plain text only.\n"
            "Do not translate, correct, or guess."
        ),
        rationale="English fallback focused on exact transcription and no guessing.",
    ),
    PromptCandidate(
        name="ENG-F2",
        text=(
            "Text Recognition:\n"
            "Read the image and transcribe only the visible text.\n"
            "Preserve the observed reading order and line breaks when clear.\n"
            "Do not translate, explain, normalize, or infer missing text."
        ),
        rationale="English fallback focused on reading order and no inference.",
    ),
    PromptCandidate(
        name="ENG-F3",
        text=(
            "Text Recognition:\n"
            "Transcribe only what is visibly present in the image.\n"
            "Output plain text only.\n"
            "If text is unclear, keep only the visible part.\n"
            "Do not repeat text."
        ),
        rationale="English fallback focused on conservative output and repetition control.",
    ),
]


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
        request_payload = self._build_request_payload(
            current_prompt=current_prompt,
            aggregate=aggregate,
            failures=failures,
            count=count,
        )

        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "minimal"},
            input=[
                {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False)},
            ],
        )

        return self._parse_and_rank_candidates(response.output_text.strip(), count=count)

    def _build_request_payload(
        self,
        *,
        current_prompt: PromptCandidate,
        aggregate: AggregateEvaluation,
        failures: list[EvaluationResult],
        count: int,
    ) -> dict[str, object]:
        limited_failures = failures[:15]
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
            for row in limited_failures
        ]
        return {
            "task": "Improve the OCR prompt while preserving plain text OCR output.",
            "prompt_language_policy": {
                "default_language": "English",
                "rule": "Prefer English prompts unless non-English wording has strong measured validation evidence.",
            },
            "prompt_shape_guidance": {
                "prefix": "Keep the 'Text Recognition:' prefix unless there is a strong reason to change it.",
                "style": "Prefer short imperative sentences over long explanations.",
                "required_rules": [
                    "Transcribe only visible text.",
                    "Output plain text only.",
                    "Do not translate, correct, normalize, or guess.",
                    "Preserve reading order and line breaks when visually clear.",
                    "Avoid repeated text.",
                ],
                "avoid": [
                    "JSON or structured extraction requests",
                    "Long task descriptions",
                    "Language-specific wording without evidence",
                    "Requests to infer missing or occluded text",
                ],
            },
            "constraints": [
                "Do not ask for JSON output.",
                "Focus on transcription rules only.",
                "Preserve plain text OCR behavior.",
                f"Return exactly {count} candidates.",
            ],
            "current_prompt": current_prompt.text,
            "aggregate_metrics": asdict(aggregate),
            "failure_summary": self._summarize_failures(limited_failures),
            "failure_examples": failure_payload,
        }

    def _summarize_failures(self, failures: list[EvaluationResult]) -> dict[str, object]:
        if not failures:
            return {
                "count_considered": 0,
                "high_non_korean_count": 0,
                "high_repetition_count": 0,
                "empty_or_garbage_count": 0,
                "avg_prediction_length": 0.0,
                "avg_reference_length": 0.0,
                "common_failure_modes": [],
            }

        avg_prediction_length = sum(len(row.predicted_text) for row in failures) / len(failures)
        avg_reference_length = sum(len(row.reference_text) for row in failures) / len(failures)
        modes = []
        if any(row.penalties.non_korean_mixed > 0 for row in failures):
            modes.append("non-target-script contamination")
        if any(row.penalties.repetition > 0 for row in failures):
            modes.append("repetition or rambling output")
        if any(row.penalties.empty_or_garbage > 0 for row in failures):
            modes.append("empty or garbage output")
        if any(len(row.predicted_text) > len(row.reference_text) * 1.5 for row in failures if row.reference_text):
            modes.append("prediction longer than reference")
        if not modes:
            modes.append("character substitution or ordering errors")

        return {
            "count_considered": len(failures),
            "high_non_korean_count": sum(1 for row in failures if row.penalties.non_korean_mixed > 0),
            "high_repetition_count": sum(1 for row in failures if row.penalties.repetition > 0),
            "empty_or_garbage_count": sum(1 for row in failures if row.penalties.empty_or_garbage > 0),
            "avg_prediction_length": round(avg_prediction_length, 2),
            "avg_reference_length": round(avg_reference_length, 2),
            "common_failure_modes": modes,
        }

    def _parse_and_rank_candidates(self, content: str, *, count: int) -> list[PromptCandidate]:
        payload = json.loads(content)
        parsed: list[PromptCandidate] = []
        seen_texts: set[str] = set()

        for index, item in enumerate(payload["candidates"], start=1):
            text = self._normalize_prompt_text(item["text"])
            if not text or text in seen_texts:
                continue
            seen_texts.add(text)
            parsed.append(
                PromptCandidate(
                    name=item.get("name", f"R{index}"),
                    text=text,
                    rationale=item.get("rationale", "").strip(),
                )
            )

        parsed.sort(key=lambda candidate: (not self._is_english_first(candidate.text), len(candidate.text)))

        for fallback in FALLBACK_CANDIDATES:
            if len(parsed) >= count:
                break
            normalized = self._normalize_prompt_text(fallback.text)
            if normalized in seen_texts:
                continue
            seen_texts.add(normalized)
            parsed.append(
                PromptCandidate(
                    name=fallback.name,
                    text=normalized,
                    rationale=fallback.rationale,
                )
            )

        return parsed[:count]

    def _normalize_prompt_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return normalized
        if not normalized.startswith("Text Recognition:"):
            normalized = f"Text Recognition:\n{normalized}"
        return normalized

    def _is_english_first(self, text: str) -> bool:
        letters = [char for char in text if char.isalpha()]
        if not letters:
            return True
        non_latin = 0
        for char in letters:
            name = unicodedata.name(char, "")
            if "LATIN" not in name:
                non_latin += 1
        return non_latin / len(letters) <= 0.1
