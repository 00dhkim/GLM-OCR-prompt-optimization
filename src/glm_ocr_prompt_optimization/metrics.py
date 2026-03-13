from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import AggregateEvaluation, EvaluationResult, PenaltyBreakdown


def character_error_rate(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0

    previous = list(range(len(hypothesis) + 1))
    for i, ref_char in enumerate(reference, start=1):
        current = [i]
        for j, hyp_char in enumerate(hypothesis, start=1):
            substitution = previous[j - 1] + (ref_char != hyp_char)
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1] / len(reference)


def _is_hangul(char: str) -> bool:
    code = ord(char)
    return 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF


def _meaningful_chars(text: str) -> list[str]:
    return [char for char in text if not char.isspace()]


def _repeated_ngram_count(tokens: list[str], n: int) -> int:
    if len(tokens) < n:
        return 0
    ngrams = [" ".join(tokens[index : index + n]) for index in range(len(tokens) - n + 1)]
    if not ngrams:
        return 0
    return max(Counter(ngrams).values())


def compute_penalties(
    predicted_text: str,
    *,
    alpha: float = 0.10,
    beta: float = 0.15,
    gamma: float = 0.15,
) -> PenaltyBreakdown:
    meaningful = _meaningful_chars(predicted_text)
    if not meaningful:
        return PenaltyBreakdown(non_korean_mixed=0.0, repetition=0.0, empty_or_garbage=gamma)

    hangul_count = sum(1 for char in meaningful if _is_hangul(char))
    cjk_count = sum(1 for char in meaningful if _is_cjk(char))
    alnum_count = sum(1 for char in meaningful if char.isalnum())

    hangul_ratio = hangul_count / len(meaningful)
    cjk_ratio = cjk_count / len(meaningful)
    meaningful_ratio = alnum_count / len(meaningful)

    non_korean = alpha if hangul_ratio < 0.25 and cjk_ratio > 0.10 else 0.0

    tokens = predicted_text.split()
    repeated = 0
    for n in (1, 2, 3):
        repeated = max(repeated, _repeated_ngram_count(tokens, n))
    repetition = beta if repeated >= 10 else 0.0

    empty_or_garbage = gamma if len(meaningful) < 3 or meaningful_ratio < 0.35 else 0.0

    return PenaltyBreakdown(
        non_korean_mixed=non_korean,
        repetition=repetition,
        empty_or_garbage=empty_or_garbage,
    )


def evaluate_prediction(
    *,
    sample_id: str,
    prompt_name: str,
    predicted_text: str,
    reference_text: str,
    image_path,
    split: str | None = None,
    alpha: float = 0.10,
    beta: float = 0.15,
    gamma: float = 0.15,
) -> EvaluationResult:
    cer = character_error_rate(reference_text, predicted_text)
    base_score = 1.0 - cer
    penalties = compute_penalties(predicted_text, alpha=alpha, beta=beta, gamma=gamma)
    total_score = base_score - penalties.total
    return EvaluationResult(
        sample_id=sample_id,
        prompt_name=prompt_name,
        cer=cer,
        base_score=base_score,
        total_score=total_score,
        penalties=penalties,
        predicted_text=predicted_text,
        reference_text=reference_text,
        image_path=image_path,
        split=split,
    )


def aggregate_evaluations(results: Iterable[EvaluationResult], prompt_text: str) -> AggregateEvaluation:
    rows = list(results)
    if not rows:
        raise ValueError("No evaluation rows to aggregate.")

    sample_count = len(rows)
    return AggregateEvaluation(
        prompt_name=rows[0].prompt_name,
        prompt_text=prompt_text,
        sample_count=sample_count,
        mean_cer=sum(row.cer for row in rows) / sample_count,
        mean_base_score=sum(row.base_score for row in rows) / sample_count,
        mean_total_score=sum(row.total_score for row in rows) / sample_count,
        non_korean_rate=sum(1 for row in rows if row.penalties.non_korean_mixed > 0) / sample_count,
        repetition_rate=sum(1 for row in rows if row.penalties.repetition > 0) / sample_count,
        empty_rate=sum(1 for row in rows if row.penalties.empty_or_garbage > 0) / sample_count,
    )
