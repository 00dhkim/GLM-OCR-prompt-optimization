import pytest

from glm_ocr_prompt_optimization.metrics import (
    character_error_rate,
    character_multiset_f1,
    compute_penalties,
    evaluate_prediction,
    normalize_ocr_text,
    normalize_unordered_text,
    token_f1,
)

pytestmark = pytest.mark.unit


def test_character_error_rate_zero_for_exact_match() -> None:
    assert character_error_rate("영수증", "영수증") == 0.0


def test_character_error_rate_handles_full_mismatch() -> None:
    assert character_error_rate("abc", "xyz") == 1.0


def test_compute_penalties_flags_repetition() -> None:
    penalties = compute_penalties("반복 " * 10)
    assert penalties.repetition > 0


def test_compute_penalties_flags_unexpected_chinese_mix() -> None:
    penalties = compute_penalties("漢字漢字漢字abc", reference_text="스타벅스")
    assert penalties.chinese_mixed > 0


def test_normalize_ocr_text_collapses_whitespace_and_nfkc() -> None:
    assert normalize_ocr_text("ＡＢＣ\n  12  3 ") == "ABC 12 3"


def test_token_f1_gives_partial_credit_for_token_overlap() -> None:
    score = token_f1("합계 12000", "합계 13000")
    assert 0.4 < score < 1.0


def test_evaluate_prediction_uses_normalized_cer() -> None:
    result = evaluate_prediction(
        sample_id="s1",
        prompt_name="baseline",
        predicted_text="합계\n12000",
        reference_text="합계 12000",
        image_path="sample.png",
    )

    assert result.raw_cer > 0.0
    assert result.cer == 0.0
    assert result.token_f1 == 1.0


def test_normalize_unordered_text_ignores_whitespace_and_order() -> None:
    assert normalize_unordered_text("김 해\n군") == normalize_unordered_text("군김해")


def test_character_multiset_f1_ignores_order() -> None:
    score = character_multiset_f1("민원 안내", "안내민원")
    assert score == 1.0


def test_evaluate_prediction_supports_unordered_character_mode() -> None:
    result = evaluate_prediction(
        sample_id="s1",
        prompt_name="baseline",
        predicted_text="안내민원",
        reference_text="민원 안내",
        image_path="sample.png",
        metadata={"evaluation_mode": "unordered_characters"},
    )

    assert result.raw_cer == 0.0
    assert result.cer == 0.0
    assert result.token_f1 == 1.0
