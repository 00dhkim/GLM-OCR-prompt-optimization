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


def test_build_analysis_payload_prefers_english_context_and_failure_summary() -> None:
    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")
    failures = _failures()
    failure_payload = optimizer._failure_payload(failures)
    failure_summary = optimizer._summarize_failures(failures)

    payload = optimizer._build_analysis_payload(
        current_prompt=PromptCandidate(name="P0", text="Text Recognition:"),
        aggregate=_aggregate(),
        failure_summary=failure_summary,
        failure_payload=failure_payload,
    )

    assert "Analyze why the OCR prompt is underperforming" in payload["task"]
    assert payload["failure_summary"]["high_chinese_count"] == 1
    assert payload["failure_summary"]["high_repetition_count"] == 1
    assert "unexpected Chinese character contamination" in payload["failure_summary"]["common_failure_modes"]
    assert "Chinese-character substitution" in payload["failure_summary"]["example_warning"]


def test_parse_and_rank_candidates_prioritizes_english_and_adds_fallbacks() -> None:
    optimizer = PromptOptimizer(api_key="test", model="gpt-5-nano")
    content = """
    {
      "candidates": [
        {"name": "K1", "text": "보이는 글자를 그대로 전사하라.", "rationale": "korean"},
        {"name": "BAD", "text": "Text Recognition:\\nUse [unclear] for unreadable text.", "rationale": "placeholder"},
        {"name": "E1", "text": "Text Recognition:\\nTranscribe only the visible text. Do not translate.", "rationale": "english"}
      ]
    }
    """

    candidates = optimizer._parse_and_rank_candidates(content, count=3)

    assert len(candidates) == 3
    assert candidates[0].text.startswith("Text Recognition:")
    assert "\n" in candidates[0].text
    assert "Transcribe only the visible text" in candidates[0].text
    assert all("[unclear]" not in candidate.text.lower() for candidate in candidates)
    assert any(candidate.name.startswith("ENG-F") for candidate in candidates)
