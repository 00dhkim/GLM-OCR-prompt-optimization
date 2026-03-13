from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class DatasetItem:
    sample_id: str
    image_path: Path
    reference_text: str
    split: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class OCRResult:
    sample_id: str
    prompt_name: str
    prompt_text: str
    predicted_text: str
    reference_text: str
    image_path: Path
    split: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PenaltyBreakdown:
    non_korean_mixed: float
    repetition: float
    empty_or_garbage: float

    @property
    def total(self) -> float:
        return self.non_korean_mixed + self.repetition + self.empty_or_garbage


@dataclass(slots=True)
class EvaluationResult:
    sample_id: str
    prompt_name: str
    cer: float
    base_score: float
    total_score: float
    penalties: PenaltyBreakdown
    predicted_text: str
    reference_text: str
    image_path: Path
    split: str | None = None


@dataclass(slots=True)
class PromptCandidate:
    name: str
    text: str
    rationale: str = ""


@dataclass(slots=True)
class PromptRoundResult:
    round_index: int
    candidates: list[PromptCandidate]
    evaluations: list["AggregateEvaluation"]


@dataclass(slots=True)
class AggregateEvaluation:
    prompt_name: str
    prompt_text: str
    sample_count: int
    mean_cer: float
    mean_base_score: float
    mean_total_score: float
    non_korean_rate: float
    repetition_rate: float
    empty_rate: float
