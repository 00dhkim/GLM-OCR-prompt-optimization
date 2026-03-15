from glm_ocr_prompt_optimization.metrics import (
    character_error_rate,
    compute_penalties,
    evaluate_prediction,
    normalize_ocr_text,
    token_f1,
)


def test_character_error_rate_zero_for_exact_match() -> None:
    assert character_error_rate("영수증", "영수증") == 0.0


def test_character_error_rate_handles_full_mismatch() -> None:
    assert character_error_rate("abc", "xyz") == 1.0


def test_compute_penalties_flags_repetition() -> None:
    penalties = compute_penalties("반복 " * 10)
    assert penalties.repetition > 0


def test_compute_penalties_flags_non_korean_cjk_mix() -> None:
    penalties = compute_penalties("漢字漢字漢字abc", reference_text="스타벅스")
    assert penalties.non_korean_mixed > 0


def test_compute_penalties_flags_empty_output() -> None:
    penalties = compute_penalties(" ", reference_text="합계 12000")
    assert penalties.empty_or_garbage > 0


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
