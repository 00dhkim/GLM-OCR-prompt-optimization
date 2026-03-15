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
    chinese_mixed: float
    repetition: float

    @property
    def total(self) -> float:
        return self.chinese_mixed + self.repetition


@dataclass(slots=True)
class EvaluationResult:
    sample_id: str
    prompt_name: str
    raw_cer: float
    cer: float
    token_f1: float
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
    metadata: dict[str, str] = field(default_factory=dict)


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
    mean_raw_cer: float
    mean_cer: float
    mean_token_f1: float
    mean_base_score: float
    mean_total_score: float
    chinese_rate: float
    repetition_rate: float


@dataclass(slots=True)
class PromptLearningExample:
    sample_id: str
    prompt_name: str
    current_prompt: str
    reference_text: str
    predicted_text: str
    evaluator_correctness: str
    evaluator_explanation: str
    error_tags: list[str]
    raw_cer: float
    cer: float
    token_f1: float
    total_score: float
    split: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PromptLearningRoundRecord:
    round_index: int
    starting_prompt: PromptCandidate
    selected_candidate: PromptCandidate
    candidates: list[PromptCandidate]
    train_aggregate: AggregateEvaluation
    candidate_aggregates: list[AggregateEvaluation]
    feedback_columns: list[str]
    learning_examples: list[PromptLearningExample]
    analysis_summary: str
    few_shot_example_count: int = 0
    rejected_candidates: dict[str, list[str]] = field(default_factory=dict)
    sanitizer_summary: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class TimingRecord:
    event_type: str
    stage: str
    total_seconds: float
    prompt_name: str | None = None
    sample_id: str | None = None
    image_path: Path | None = None
    split: str | None = None
    round_index: int | None = None
    preprocess_seconds: float = 0.0
    request_seconds: float = 0.0
    evaluation_seconds: float = 0.0
    sample_count: int = 0
    attempt_count: int = 0
