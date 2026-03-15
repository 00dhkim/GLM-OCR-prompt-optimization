from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable

from .models import AggregateEvaluation, EvaluationResult, PenaltyBreakdown


def normalize_ocr_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in normalized.split("\n")]
    lines = [line for line in lines if line]
    return " ".join(lines).strip()


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


def token_f1(reference: str, hypothesis: str) -> float:
    ref_tokens = normalize_ocr_text(reference).split()
    hyp_tokens = normalize_ocr_text(hypothesis).split()
    if not ref_tokens and not hyp_tokens:
        return 1.0
    if not ref_tokens or not hyp_tokens:
        return 0.0

    ref_counter = Counter(ref_tokens)
    hyp_counter = Counter(hyp_tokens)
    overlap = sum(min(ref_counter[token], hyp_counter[token]) for token in ref_counter)
    precision = overlap / len(hyp_tokens)
    recall = overlap / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


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


def _has_suspicious_char_run(text: str, *, min_run: int = 6) -> bool:
    return bool(re.search(r"(.)\1{" + str(min_run - 1) + r",}", text))


def compute_penalties(
    predicted_text: str,
    *,
    reference_text: str = "",
    alpha: float = 0.10,
    beta: float = 0.15,
    gamma: float = 0.15,
) -> PenaltyBreakdown:
    meaningful = _meaningful_chars(predicted_text)
    if not meaningful:
        return PenaltyBreakdown(non_korean_mixed=0.0, repetition=0.0, empty_or_garbage=gamma)

    reference_meaningful = _meaningful_chars(reference_text)
    predicted_hangul = sum(1 for char in meaningful if _is_hangul(char))
    predicted_cjk = sum(1 for char in meaningful if _is_cjk(char))
    reference_cjk = sum(1 for char in reference_meaningful if _is_cjk(char))
    alnum_count = sum(1 for char in meaningful if char.isalnum())

    predicted_cjk_ratio = predicted_cjk / len(meaningful)
    reference_cjk_ratio = reference_cjk / len(reference_meaningful) if reference_meaningful else 0.0

    unexpected_cjk = predicted_cjk_ratio > 0.10 and reference_cjk_ratio < 0.05
    non_korean = alpha if unexpected_cjk else 0.0

    tokens = normalize_ocr_text(predicted_text).split()
    repeated = 0
    for n in (1, 2, 3):
        repeated = max(repeated, _repeated_ngram_count(tokens, n))
    repetition_threshold = 4 if len(tokens) < 20 else 6
    repetition = beta if repeated >= repetition_threshold or _has_suspicious_char_run(predicted_text) else 0.0

    meaningful_ratio = alnum_count / len(meaningful)
    min_expected_length = max(3, int(len(reference_meaningful) * 0.15)) if reference_meaningful else 3
    too_short = len(meaningful) < min_expected_length
    mostly_noise = meaningful_ratio < 0.25 and predicted_hangul + predicted_cjk < max(1, len(meaningful) // 4)
    empty_or_garbage = gamma if too_short or mostly_noise else 0.0

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
    raw_cer = character_error_rate(reference_text, predicted_text)
    normalized_reference = normalize_ocr_text(reference_text)
    normalized_predicted = normalize_ocr_text(predicted_text)
    cer = character_error_rate(normalized_reference, normalized_predicted)
    token_score = token_f1(reference_text, predicted_text)
    base_score = 0.85 * (1.0 - cer) + 0.15 * token_score
    penalties = compute_penalties(
        predicted_text,
        reference_text=reference_text,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
    )
    total_score = base_score - penalties.total
    return EvaluationResult(
        sample_id=sample_id,
        prompt_name=prompt_name,
        raw_cer=raw_cer,
        cer=cer,
        token_f1=token_score,
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
        mean_raw_cer=sum(row.raw_cer for row in rows) / sample_count,
        mean_cer=sum(row.cer for row in rows) / sample_count,
        mean_token_f1=sum(row.token_f1 for row in rows) / sample_count,
        mean_base_score=sum(row.base_score for row in rows) / sample_count,
        mean_total_score=sum(row.total_score for row in rows) / sample_count,
        non_korean_rate=sum(1 for row in rows if row.penalties.non_korean_mixed > 0) / sample_count,
        repetition_rate=sum(1 for row in rows if row.penalties.repetition > 0) / sample_count,
        empty_rate=sum(1 for row in rows if row.penalties.empty_or_garbage > 0) / sample_count,
    )
