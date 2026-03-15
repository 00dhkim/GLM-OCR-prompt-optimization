from pathlib import Path

import pytest

from glm_ocr_prompt_optimization.models import AggregateEvaluation, EvaluationResult, PenaltyBreakdown, PromptCandidate
from glm_ocr_prompt_optimization.optimizer import PromptOptimizer

pytestmark = pytest.mark.unit


def _aggregate() -> AggregateEvaluation:
    return AggregateEvaluation(
        prompt_name="P0",
        prompt_text="Text Recognition:",
        sample_count=3,
        mean_raw_cer=0.45,
        mean_cer=0.4,
        mean_token_f1=0.6,
        mean_base_score=0.6,
        mean_total_score=0.55,
        chinese_rate=0.33,
        repetition_rate=0.33,
    )


def _failures() -> list[EvaluationResult]:
    return [
        EvaluationResult(
            sample_id="s1",
            prompt_name="P0",
            raw_cer=0.8,
            cer=0.8,
            token_f1=0.0,
            base_score=0.2,
            total_score=0.0,
            penalties=PenaltyBreakdown(chinese_mixed=0.2, repetition=0.0),
            predicted_text="漢字 abc",
            reference_text="스타벅스",
            image_path=Path("sample.png"),
            split="dev",
        ),
        EvaluationResult(
            sample_id="s2",
            prompt_name="P0",
            raw_cer=0.7,
            cer=0.7,
            token_f1=0.2,
            base_score=0.3,
            total_score=0.0,
            penalties=PenaltyBreakdown(chinese_mixed=0.0, repetition=0.2),
            predicted_text="합계 합계 합계 합계",
            reference_text="합계",
            image_path=Path("sample.png"),
            split="dev",
        ),
    ]


def test_generate_candidates_uses_prompt_learning_sdk(monkeypatch) -> None:
    seen = {}

    class FakePromptLearningOptimizer:
        def __init__(self, *args, **kwargs):
            seen["init"] = kwargs

        def create_annotation(self, **kwargs):
            seen["annotation"] = kwargs
            return ["annotation"]

        def optimize(self, **kwargs):
            seen["optimize"] = kwargs
            return (
                "YOUR NEW PROMPT:\n"
                "Text Recognition:\n"
                "- Transcribe only the visible text.\n"
                "- Output plain text only.\n"
                "- Do not translate.\n"
                "- Output examples (for reference only; produce exact transcripts for your inputs):\n"
                "- Example 1: [data sample] -> [transcription]\n"
                "```markdown"
            )

    monkeypatch.setattr("glm_ocr_prompt_optimization.optimizer.PromptLearningOptimizer", FakePromptLearningOptimizer)

    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")
    candidates = optimizer.generate_candidates(
        current_prompt=PromptCandidate(name="P0", text="Text Recognition:"),
        aggregate=_aggregate(),
        failures=_failures(),
        count=3,
    )

    assert len(candidates) == 3
    assert all("YOUR NEW PROMPT" not in candidate.text for candidate in candidates)
    assert all("```" not in candidate.text for candidate in candidates)
    assert all("[data sample]" not in candidate.text for candidate in candidates)
    assert seen["annotation"]["output_column"] == "predicted_text"
    assert seen["optimize"]["feedback_columns"] == [
        "evaluator_correctness",
        "evaluator_explanation",
        "error_tags",
    ]
    assert optimizer.last_learning_context is not None
    assert optimizer.last_learning_context["dataset_records"][0]["contains_markdown"] == "false"


def test_build_learning_examples_from_failures_extracts_feedback_tags() -> None:
    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")
    learning_examples = optimizer._build_learning_examples_from_failures(
        current_prompt=PromptCandidate(name="P0", text="Text Recognition:"),
        failures=_failures(),
    )

    assert len(learning_examples) == 2
    assert learning_examples[0].evaluator_correctness == "fail"
    assert "script_substitution" in learning_examples[0].error_tags
    assert "repetition" in learning_examples[1].error_tags
    assert learning_examples[1].metadata["output_length_ratio"] == "5.50"


def test_sanitize_prompt_removes_scaffolding_and_examples() -> None:
    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")
    sanitized, applied = optimizer._sanitize_prompt(
        "YOUR NEW PROMPT:\nText Recognition:\n- Output plain text only.\n- Example 1: [data sample] -> [transcription]\n```markdown",
        "Text Recognition:",
    )

    assert "YOUR NEW PROMPT" not in sanitized
    assert "[data sample]" not in sanitized
    assert "```" not in sanitized
    assert "remove_scaffolding_header" in applied
    assert "remove_examples" in applied
