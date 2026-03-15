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


def normalize_unordered_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    meaningful = [char for char in normalized if not char.isspace()]
    return "".join(sorted(meaningful))


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


def character_multiset_f1(reference: str, hypothesis: str) -> float:
    ref_chars = Counter(normalize_unordered_text(reference))
    hyp_chars = Counter(normalize_unordered_text(hypothesis))
    if not ref_chars and not hyp_chars:
        return 1.0
    if not ref_chars or not hyp_chars:
        return 0.0

    overlap = sum(min(ref_chars[char], hyp_chars[char]) for char in ref_chars)
    precision = overlap / sum(hyp_chars.values())
    recall = overlap / sum(ref_chars.values())
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _is_hangul(char: str) -> bool:
    code = ord(char)
    return 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F


def _is_chinese(char: str) -> bool:
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
) -> PenaltyBreakdown:
    meaningful = _meaningful_chars(predicted_text)
    if not meaningful:
        return PenaltyBreakdown(chinese_mixed=0.0, repetition=0.0)

    reference_meaningful = _meaningful_chars(reference_text)
    predicted_chinese = sum(1 for char in meaningful if _is_chinese(char))
    reference_chinese = sum(1 for char in reference_meaningful if _is_chinese(char))

    predicted_chinese_ratio = predicted_chinese / len(meaningful)
    reference_chinese_ratio = reference_chinese / len(reference_meaningful) if reference_meaningful else 0.0

    unexpected_chinese = predicted_chinese_ratio > 0.10 and reference_chinese_ratio < 0.05
    chinese_mixed = alpha if unexpected_chinese else 0.0

    tokens = normalize_ocr_text(predicted_text).split()
    repeated = 0
    for n in (1, 2, 3):
        repeated = max(repeated, _repeated_ngram_count(tokens, n))
    repetition_threshold = 4 if len(tokens) < 20 else 6
    repetition = beta if repeated >= repetition_threshold or _has_suspicious_char_run(predicted_text) else 0.0
    markdown_leakage = 0.10 if "```" in predicted_text or "`" in predicted_text else 0.0
    lowered = predicted_text.lower()
    instruction_echo = 0.08 if any(marker in lowered for marker in ("text recognition", "transcribe", "output plain text only")) else 0.0

    return PenaltyBreakdown(
        chinese_mixed=chinese_mixed,
        repetition=repetition,
        markdown_leakage=markdown_leakage,
        instruction_echo=instruction_echo,
    )


def evaluate_prediction(
    *,
    sample_id: str,
    prompt_name: str,
    predicted_text: str,
    reference_text: str,
    image_path,
    split: str | None = None,
    metadata: dict[str, str] | None = None,
    alpha: float = 0.10,
    beta: float = 0.15,
) -> EvaluationResult:
    metadata = metadata or {}
    evaluation_mode = metadata.get("evaluation_mode", "default")
    predicted_line_count = max(1, predicted_text.count("\n") + 1)
    reference_line_count = max(1, reference_text.count("\n") + 1)
    contains_markdown = "```" in predicted_text or "`" in predicted_text
    lowered = predicted_text.lower()
    instruction_echo = any(marker in lowered for marker in ("text recognition", "transcribe", "output plain text only"))
    reference_digit_ratio = sum(char.isdigit() for char in reference_text) / len(reference_text) if reference_text else 0.0
    if "." in reference_text and any(char.isdigit() for char in reference_text):
        field_type_hint = "date"
    elif any(char in reference_text for char in ("동", "로", "길", "번")):
        field_type_hint = "address"
    elif reference_digit_ratio >= 0.5:
        field_type_hint = "numeric"
    elif any(char.isdigit() for char in reference_text) and any(char.isalpha() for char in reference_text):
        field_type_hint = "mixed"
    else:
        field_type_hint = "general"

    if evaluation_mode == "unordered_characters":
        normalized_reference = normalize_unordered_text(reference_text)
        normalized_predicted = normalize_unordered_text(predicted_text)
        raw_cer = character_error_rate(normalized_reference, normalized_predicted)
        cer = raw_cer
        token_score = character_multiset_f1(reference_text, predicted_text)
    else:
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
        contains_markdown=contains_markdown,
        instruction_echo=instruction_echo,
        field_type_hint=field_type_hint,
        digit_heavy=reference_digit_ratio >= 0.5,
        line_break_mismatch=predicted_line_count != reference_line_count,
    )


def aggregate_evaluations(results: Iterable[EvaluationResult], prompt_text: str) -> AggregateEvaluation:
    rows = list(results)
    if not rows:
        raise ValueError("No evaluation rows to aggregate.")

    sample_count = len(rows)
    numeric_rows = [row for row in rows if row.digit_heavy or row.field_type_hint == "numeric"]
    non_numeric_rows = [row for row in rows if row not in numeric_rows]
    return AggregateEvaluation(
        prompt_name=rows[0].prompt_name,
        prompt_text=prompt_text,
        sample_count=sample_count,
        mean_raw_cer=sum(row.raw_cer for row in rows) / sample_count,
        mean_cer=sum(row.cer for row in rows) / sample_count,
        mean_token_f1=sum(row.token_f1 for row in rows) / sample_count,
        mean_base_score=sum(row.base_score for row in rows) / sample_count,
        mean_total_score=sum(row.total_score for row in rows) / sample_count,
        chinese_rate=sum(1 for row in rows if row.penalties.chinese_mixed > 0) / sample_count,
        repetition_rate=sum(1 for row in rows if row.penalties.repetition > 0) / sample_count,
        markdown_leakage_rate=sum(1 for row in rows if row.contains_markdown) / sample_count,
        instruction_echo_rate=sum(1 for row in rows if row.instruction_echo) / sample_count,
        line_break_match_rate=sum(1 for row in rows if not row.line_break_mismatch) / sample_count,
        numeric_field_cer=sum(row.cer for row in numeric_rows) / len(numeric_rows) if numeric_rows else 0.0,
        non_numeric_field_cer=sum(row.cer for row in non_numeric_rows) / len(non_numeric_rows) if non_numeric_rows else 0.0,
    )
