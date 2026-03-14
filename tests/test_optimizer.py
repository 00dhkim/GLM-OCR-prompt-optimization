from pathlib import Path

from glm_ocr_prompt_optimization.models import AggregateEvaluation, EvaluationResult, PenaltyBreakdown, PromptCandidate
from glm_ocr_prompt_optimization.optimizer import PromptOptimizer


def _aggregate() -> AggregateEvaluation:
    return AggregateEvaluation(
        prompt_name="P0",
        prompt_text="Text Recognition:",
        sample_count=3,
        mean_cer=0.4,
        mean_base_score=0.6,
        mean_total_score=0.55,
        non_korean_rate=0.33,
        repetition_rate=0.33,
        empty_rate=0.0,
    )


def _failures() -> list[EvaluationResult]:
    return [
        EvaluationResult(
            sample_id="s1",
            prompt_name="P0",
            cer=0.8,
            base_score=0.2,
            total_score=0.0,
            penalties=PenaltyBreakdown(non_korean_mixed=0.2, repetition=0.0, empty_or_garbage=0.0),
            predicted_text="漢字 abc",
            reference_text="스타벅스",
            image_path=Path("sample.png"),
            split="dev",
        ),
        EvaluationResult(
            sample_id="s2",
            prompt_name="P0",
            cer=0.7,
            base_score=0.3,
            total_score=0.0,
            penalties=PenaltyBreakdown(non_korean_mixed=0.0, repetition=0.2, empty_or_garbage=0.0),
            predicted_text="합계 합계 합계 합계",
            reference_text="합계",
            image_path=Path("sample.png"),
            split="dev",
        ),
    ]


def test_build_request_payload_prefers_english_and_includes_failure_summary() -> None:
    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")

    payload = optimizer._build_request_payload(
        current_prompt=PromptCandidate(name="P0", text="Text Recognition:"),
        aggregate=_aggregate(),
        failures=_failures(),
        count=4,
    )

    policy = payload["prompt_language_policy"]
    summary = payload["failure_summary"]

    assert policy["default_language"] == "English"
    assert "Prefer English prompts" in policy["rule"]
    assert summary["high_non_korean_count"] == 1
    assert summary["high_repetition_count"] == 1
    assert "non-target-script contamination" in summary["common_failure_modes"]


def test_parse_and_rank_candidates_prioritizes_english_and_adds_fallbacks() -> None:
    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")
    content = """
    {
      "candidates": [
        {"name": "K1", "text": "보이는 글자를 그대로 전사하라.", "rationale": "korean"},
        {"name": "E1", "text": "Transcribe only the visible text. Do not translate.", "rationale": "english"}
      ]
    }
    """

    candidates = optimizer._parse_and_rank_candidates(content, count=3)

    assert len(candidates) == 3
    assert candidates[0].text.startswith("Text Recognition:")
    assert "Transcribe only the visible text" in candidates[0].text
    assert any(candidate.name.startswith("ENG-F") for candidate in candidates)
