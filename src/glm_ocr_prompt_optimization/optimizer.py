from __future__ import annotations

import json
import unicodedata
from dataclasses import asdict, dataclass

from openai import OpenAI

from .models import AggregateEvaluation, EvaluationResult, PromptCandidate


ANALYSIS_SYSTEM_PROMPT = """You analyze OCR prompt failures before rewriting prompts.
Return strict JSON with top-level keys:
- issues: list of objects with name, severity, evidence, and instruction
- keep: list of strengths to preserve from the current prompt
- avoid: list of prompt patterns to avoid next
- rewrite_strategy: short paragraph
Prefer compact, evidence-based analysis. Do not write candidate prompts yet.
"""

OPTIMIZER_SYSTEM_PROMPT = """You optimize prompts for plain-text OCR.
Return strict JSON with a top-level key named "candidates".
Each candidate must contain "name", "text", and "rationale".
Prefer concise prompts written in English.
The prompt is for transcription only, not extraction or JSON formatting.
Each candidate prompt must be at most 1024 characters long, including the "Text Recognition:" prefix.
Strong candidates usually:
- say to transcribe only visible text
- require plain text output only
- forbid translation, correction, normalization, and guessing
- forbid substituting Korean text with Chinese characters or other scripts
- preserve reading order and line breaks when visually clear
- forbid repeated text
- forbid placeholders such as [unclear], [unreadable], or invented markers
"""

FALLBACK_ANALYSIS = {
    "issues": [
        {
            "name": "character substitution, ordering errors, or script contamination",
            "severity": "medium",
            "evidence": "Top failures show mismatched characters despite non-empty output.",
            "instruction": "Use a short transcription-only prompt, avoid interpretation, and forbid Chinese-character substitution.",
        }
    ],
    "keep": ["The task should stay plain-text OCR only."],
    "avoid": ["Long prompts that add explanation or extraction behavior."],
    "rewrite_strategy": "Keep the prompt short, imperative, and English-first. Emphasize visible-text transcription only.",
}

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

MAX_PROMPT_LENGTH = 1024


@dataclass(slots=True)
class FailureExample:
    sample_id: str
    reference_text: str
    predicted_text: str
    raw_cer: float
    cer: float
    token_f1: float
    chinese_penalty: float
    repetition_penalty: float


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
        failure_payload = self._failure_payload(failures[:15])
        failure_summary = self._summarize_failures(failures[:15])
        analysis = self._analyze_failures(
            current_prompt=current_prompt,
            aggregate=aggregate,
            failure_summary=failure_summary,
            failure_payload=failure_payload,
        )
        request_payload = self._build_candidate_request_payload(
            current_prompt=current_prompt,
            aggregate=aggregate,
            failure_summary=failure_summary,
            failure_payload=failure_payload,
            analysis=analysis,
            count=count,
        )

        try:
            response_text = self._request_candidates(request_payload)
            candidates = self._parse_and_rank_candidates(response_text.strip(), count=count, fill_fallbacks=False)
            if len(candidates) < count:
                retry_payload = self._build_regeneration_payload(
                    base_payload=request_payload,
                    accepted_candidates=candidates,
                    shortage=count - len(candidates),
                )
                retry_text = self._request_candidates(retry_payload)
                merged = self._merge_candidates(
                    existing=candidates,
                    incoming=self._parse_and_rank_candidates(retry_text.strip(), count=count, fill_fallbacks=False),
                    count=count,
                )
                return merged
            return self._merge_candidates(existing=candidates, incoming=[], count=count)
        except Exception:
            return self._fallback_candidates(count)

    def _request_candidates(self, payload: dict[str, object]) -> str:
        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "minimal"},
            input=[
                {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        return response.output_text

    def _analyze_failures(
        self,
        *,
        current_prompt: PromptCandidate,
        aggregate: AggregateEvaluation,
        failure_summary: dict[str, object],
        failure_payload: list[dict[str, object]],
    ) -> dict[str, object]:
        request_payload = self._build_analysis_payload(
            current_prompt=current_prompt,
            aggregate=aggregate,
            failure_summary=failure_summary,
            failure_payload=failure_payload,
        )
        try:
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": "minimal"},
                input=[
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False)},
                ],
            )
            payload = json.loads(response.output_text.strip())
            if not isinstance(payload.get("issues"), list):
                return FALLBACK_ANALYSIS
            return payload
        except Exception:
            return FALLBACK_ANALYSIS

    def _build_analysis_payload(
        self,
        *,
        current_prompt: PromptCandidate,
        aggregate: AggregateEvaluation,
        failure_summary: dict[str, object],
        failure_payload: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "task": "Analyze why the OCR prompt is underperforming and what prompt changes are justified.",
            "current_prompt": current_prompt.text,
            "aggregate_metrics": asdict(aggregate),
            "failure_summary": failure_summary,
            "failure_examples": failure_payload,
            "analysis_requirements": [
                "Explain what to preserve from the current prompt.",
                "Identify the top error categories with evidence.",
                "Recommend prompt edits, not model changes.",
                "Assume prompt language should stay English unless evidence suggests otherwise.",
            ],
        }

    def _build_candidate_request_payload(
        self,
        *,
        current_prompt: PromptCandidate,
        aggregate: AggregateEvaluation,
        failure_summary: dict[str, object],
        failure_payload: list[dict[str, object]],
        analysis: dict[str, object],
        count: int,
    ) -> dict[str, object]:
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
                    "Do not substitute Korean text with Chinese characters or other scripts.",
                    "Preserve reading order and line breaks when visually clear.",
                    "Avoid repeated text.",
                    "If some text is unclear, keep only the visible portion and do not insert placeholders.",
                ],
                "avoid": [
                    "JSON or structured extraction requests",
                    "Long task descriptions",
                    "Language-specific wording without evidence",
                    "Requests to infer missing or occluded text",
                    "Chinese-character or Hanzi substitution for Korean text",
                    "Placeholders such as [unclear], [unreadable], ???, or invented markers",
                ],
            },
            "constraints": [
                "Do not ask for JSON output.",
                "Focus on transcription rules only.",
                "Preserve plain text OCR behavior.",
                "Do not drift far from the current prompt unless failures strongly justify it.",
                "Do not substitute Korean text with Chinese characters or Hanzi.",
                "Do not use placeholders or bracketed markers for unreadable text.",
                "If text is unclear, prefer omitting the unreadable part over inventing substitute markers.",
                f"Each candidate prompt must be at most {MAX_PROMPT_LENGTH} characters long, including the prefix.",
                f"Return exactly {count} candidates.",
            ],
            "current_prompt": current_prompt.text,
            "aggregate_metrics": asdict(aggregate),
            "failure_summary": failure_summary,
            "failure_examples": failure_payload,
            "analysis": analysis,
        }

    def _build_regeneration_payload(
        self,
        *,
        base_payload: dict[str, object],
        accepted_candidates: list[PromptCandidate],
        shortage: int,
    ) -> dict[str, object]:
        payload = dict(base_payload)
        payload["task"] = "Generate replacement OCR prompt candidates to fill the missing slots."
        payload["constraints"] = [
            *list(base_payload.get("constraints", [])),
            f"Return exactly {shortage} replacement candidates.",
            "Do not repeat any accepted candidate text.",
            "If a previous candidate was too long, rewrite it into a shorter prompt instead of expanding it.",
        ]
        payload["accepted_candidates"] = [
            {"name": candidate.name, "text": candidate.text, "length": len(candidate.text)}
            for candidate in accepted_candidates
        ]
        return payload

    def _failure_payload(self, failures: list[EvaluationResult]) -> list[dict[str, object]]:
        return [
            asdict(
                FailureExample(
                    sample_id=row.sample_id,
                    reference_text=row.reference_text,
                    predicted_text=row.predicted_text,
                    raw_cer=row.raw_cer,
                    cer=row.cer,
                    token_f1=row.token_f1,
                    chinese_penalty=row.penalties.chinese_mixed,
                    repetition_penalty=row.penalties.repetition,
                )
            )
            for row in failures
        ]

    def _summarize_failures(self, failures: list[EvaluationResult]) -> dict[str, object]:
        if not failures:
            return {
                "count_considered": 0,
                "high_chinese_count": 0,
                "high_repetition_count": 0,
                "avg_prediction_length": 0.0,
                "avg_reference_length": 0.0,
                "avg_raw_cer": 0.0,
                "avg_normalized_cer": 0.0,
                "avg_token_f1": 0.0,
                "common_failure_modes": [],
            }

        avg_prediction_length = sum(len(row.predicted_text) for row in failures) / len(failures)
        avg_reference_length = sum(len(row.reference_text) for row in failures) / len(failures)
        modes = []
        if any(row.penalties.chinese_mixed > 0 for row in failures):
            modes.append("unexpected Chinese character contamination")
        if any(row.penalties.repetition > 0 for row in failures):
            modes.append("repetition or rambling output")
        if any(len(row.predicted_text) > len(row.reference_text) * 1.5 for row in failures if row.reference_text):
            modes.append("prediction longer than reference")
        if not modes:
            modes.append("character substitution or ordering errors")

        return {
            "count_considered": len(failures),
            "high_chinese_count": sum(1 for row in failures if row.penalties.chinese_mixed > 0),
            "high_repetition_count": sum(1 for row in failures if row.penalties.repetition > 0),
            "avg_prediction_length": round(avg_prediction_length, 2),
            "avg_reference_length": round(avg_reference_length, 2),
            "avg_raw_cer": round(sum(row.raw_cer for row in failures) / len(failures), 4),
            "avg_normalized_cer": round(sum(row.cer for row in failures) / len(failures), 4),
            "avg_token_f1": round(sum(row.token_f1 for row in failures) / len(failures), 4),
            "common_failure_modes": modes,
            "example_warning": "If Korean text is present, avoid Chinese-character substitution such as Hanzi output.",
        }

    def _parse_and_rank_candidates(
        self,
        content: str,
        *,
        count: int,
        fill_fallbacks: bool = True,
    ) -> list[PromptCandidate]:
        payload = json.loads(content)
        parsed: list[PromptCandidate] = []
        seen_texts: set[str] = set()

        for index, item in enumerate(payload["candidates"], start=1):
            text = self._normalize_prompt_text(item["text"])
            if not text or text in seen_texts:
                continue
            if len(text) > MAX_PROMPT_LENGTH:
                continue
            seen_texts.add(text)
            parsed.append(
                PromptCandidate(
                    name=item.get("name", f"R{index}"),
                    text=text,
                    rationale=item.get("rationale", "").strip(),
                )
            )

        parsed = [candidate for candidate in parsed if not self._contains_placeholder(candidate.text)]
        parsed.sort(
            key=lambda candidate: (
                not self._is_english_first(candidate.text),
                self._contains_placeholder(candidate.text),
                len(candidate.text),
            )
        )

        if fill_fallbacks:
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

    def _merge_candidates(
        self,
        *,
        existing: list[PromptCandidate],
        incoming: list[PromptCandidate],
        count: int,
    ) -> list[PromptCandidate]:
        merged: list[PromptCandidate] = []
        seen_texts: set[str] = set()
        for candidate in [*existing, *incoming]:
            if candidate.text in seen_texts:
                continue
            seen_texts.add(candidate.text)
            merged.append(candidate)
            if len(merged) >= count:
                break
        if len(merged) < count:
            for fallback in self._fallback_candidates(count):
                if fallback.text in seen_texts:
                    continue
                seen_texts.add(fallback.text)
                merged.append(fallback)
                if len(merged) >= count:
                    break
        return merged[:count]

    def _fallback_candidates(self, count: int) -> list[PromptCandidate]:
        return [
            PromptCandidate(name=item.name, text=self._normalize_prompt_text(item.text), rationale=item.rationale)
            for item in FALLBACK_CANDIDATES[:count]
        ]

    def _normalize_prompt_text(self, text: str) -> str:
        normalized = text.strip().replace("\\r\\n", "\n").replace("\\n", "\n")
        if not normalized:
            return normalized
        if not normalized.startswith("Text Recognition:"):
            normalized = f"Text Recognition:\n{normalized}"
        return normalized

    def _contains_placeholder(self, text: str) -> bool:
        lowered = text.lower()
        markers = ("[unclear]", "[unreadable]", "[illegible]", "???", "<unclear>", "<unreadable>")
        return any(marker in lowered for marker in markers)

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
