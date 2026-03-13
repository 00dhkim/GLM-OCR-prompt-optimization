from glm_ocr_prompt_optimization.metrics import character_error_rate, compute_penalties


def test_character_error_rate_zero_for_exact_match() -> None:
    assert character_error_rate("영수증", "영수증") == 0.0


def test_character_error_rate_handles_full_mismatch() -> None:
    assert character_error_rate("abc", "xyz") == 1.0


def test_compute_penalties_flags_repetition() -> None:
    penalties = compute_penalties("반복 " * 10)
    assert penalties.repetition > 0


def test_compute_penalties_flags_non_korean_cjk_mix() -> None:
    penalties = compute_penalties("漢字漢字漢字abc")
    assert penalties.non_korean_mixed > 0


def test_compute_penalties_flags_empty_output() -> None:
    penalties = compute_penalties(" ")
    assert penalties.empty_or_garbage > 0
