from __future__ import annotations

import hashlib
import itertools
import re

import pandas as pd
from optimizer_sdk.prompt_learning_optimizer import PromptLearningOptimizer
from phoenix.client.types import PromptVersion

from .arize_logger import ArizeLogger
from .models import AggregateEvaluation, EvaluationResult, PromptCandidate, PromptLearningExample


ANNOTATOR_PROMPTS = [
    (
        "You are analyzing OCR prompt behavior. Summarize the highest-value instruction changes that would prevent "
        "the observed transcription failures without turning the task into extraction or translation."
    ),
    (
        "Review the OCR outputs and evaluator feedback. Produce concise annotations about repeated failure modes, "
        "especially script substitution, repetition, omission, and line-order mistakes."
    ),
]


class PromptOptimizer:
    def __init__(self, *, api_key: str, model: str, arize_logger: ArizeLogger | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._arize_logger = arize_logger
        self._last_learning_context: dict[str, object] | None = None

    @property
    def last_learning_context(self) -> dict[str, object] | None:
        return self._last_learning_context

    def generate_candidates(
        self,
        *,
        current_prompt: PromptCandidate,
        aggregate: AggregateEvaluation,
        failures: list[EvaluationResult],
        count: int = 5,
        learning_examples: list[PromptLearningExample] | None = None,
        feedback_columns: list[str] | None = None,
        task_description: str = "Optimize an OCR transcription prompt using evaluator feedback.",
        candidate_strategy: str = "ocr-rules",
    ) -> list[PromptCandidate]:
        examples = learning_examples or self._build_learning_examples_from_failures(
            current_prompt=current_prompt,
            failures=failures,
        )
        feedback_columns = feedback_columns or [
            "evaluator_correctness",
            "evaluator_explanation",
            "error_tags",
            "failure_mode_summary",
            "suggested_instruction_change",
            "field_risk",
        ]
        dataset = self._dataset_from_learning_examples(examples)
        annotations = self._create_annotations(
            current_prompt=current_prompt,
            dataset=dataset,
            feedback_columns=feedback_columns,
        )
        optimized = self._run_prompt_learning(
            current_prompt=current_prompt,
            dataset=dataset,
            feedback_columns=feedback_columns,
            annotations=annotations,
        )
        optimized_text = self._extract_prompt_text(optimized)
        candidates = self._expand_candidate_variants(
            raw_prompt=optimized_text,
            current_prompt=current_prompt,
            count=count,
            rationale=task_description,
            annotations=annotations,
            learning_examples=examples,
            candidate_strategy=candidate_strategy,
        )
        self._last_learning_context = {
            "aggregate_metrics": {
                "mean_total_score": aggregate.mean_total_score,
                "mean_cer": aggregate.mean_cer,
            },
            "feedback_columns": feedback_columns,
            "annotations": annotations,
            "dataset_records": dataset.to_dict(orient="records"),
            "raw_candidate_text": optimized_text,
            "sanitized_candidates": [candidate.metadata for candidate in candidates],
            "candidate_strategy": candidate_strategy,
            "few_shot_examples": [example.sample_id for example in examples if example.representative],
        }
        return candidates

    def _create_annotations(
        self,
        *,
        current_prompt: PromptCandidate,
        dataset: pd.DataFrame,
        feedback_columns: list[str],
    ) -> list[str]:
        optimizer = PromptLearningOptimizer(
            prompt=current_prompt.text,
            model_choice=self._model,
            openai_api_key=self._api_key,
        )
        try:
            return optimizer.create_annotation(
                prompt=current_prompt.text,
                template_variables=[],
                dataset=dataset,
                feedback_columns=feedback_columns,
                annotator_prompts=ANNOTATOR_PROMPTS,
                output_column="predicted_text",
                ground_truth_column="reference_text",
            )
        except Exception:
            return []

    def _run_prompt_learning(
        self,
        *,
        current_prompt: PromptCandidate,
        dataset: pd.DataFrame,
        feedback_columns: list[str],
        annotations: list[str],
    ) -> PromptVersion | list[dict[str, str]] | str:
        prompt_object: PromptVersion | str
        prompt_object = current_prompt.text
        if self._arize_logger and self._arize_logger.enabled:
            prompt_version = self._arize_logger.create_prompt_version(
                prompt=current_prompt,
                description="OCR prompt under optimization via Arize Prompt Learning SDK",
                metadata=current_prompt.metadata or None,
            )
            if prompt_version is not None:
                prompt_object = prompt_version

        optimizer = PromptLearningOptimizer(
            prompt=prompt_object,
            model_choice=self._model,
            openai_api_key=self._api_key,
            verbose=False,
        )
        return optimizer.optimize(
            dataset=dataset,
            output_column="predicted_text",
            feedback_columns=feedback_columns,
            annotations=annotations,
            context_size_k=128000,
        )

    def _dataset_from_learning_examples(self, examples: list[PromptLearningExample]) -> pd.DataFrame:
        rows = []
        for row in examples:
            metadata = row.metadata or {}
            rows.append(
                {
                    "sample_id": row.sample_id,
                    "predicted_text": row.predicted_text,
                    "reference_text": row.reference_text,
                    "evaluator_correctness": row.evaluator_correctness,
                    "evaluator_explanation": row.evaluator_explanation,
                    "error_tags": ", ".join(row.error_tags),
                    "split": row.split or "",
                    "output_length_ratio": metadata.get("output_length_ratio", "1.00"),
                    "contains_markdown": metadata.get("contains_markdown", "false"),
                    "instruction_echo": metadata.get("instruction_echo", "false"),
                    "field_type_hint": metadata.get("field_type_hint", "general"),
                    "digit_heavy": metadata.get("digit_heavy", "false"),
                    "line_break_error": metadata.get("line_break_error", "false"),
                    "failure_mode_summary": metadata.get("failure_mode_summary", ""),
                    "suggested_instruction_change": metadata.get("suggested_instruction_change", ""),
                    "field_risk": metadata.get("field_risk", "general"),
                }
            )
        return pd.DataFrame(rows)

    def _expand_candidate_variants(
        self,
        *,
        raw_prompt: str,
        current_prompt: PromptCandidate,
        count: int,
        rationale: str,
        annotations: list[str],
        learning_examples: list[PromptLearningExample],
        candidate_strategy: str,
    ) -> list[PromptCandidate]:
        if candidate_strategy == "legacy":
            return self._expand_legacy_variants(
                raw_prompt=raw_prompt,
                current_prompt=current_prompt,
                count=count,
                rationale=rationale,
            )
        return self._expand_rule_variants(
            raw_prompt=raw_prompt,
            current_prompt=current_prompt,
            count=count,
            rationale=rationale,
            annotations=annotations,
            learning_examples=learning_examples,
        )

    def _expand_legacy_variants(
        self,
        *,
        raw_prompt: str,
        current_prompt: PromptCandidate,
        count: int,
        rationale: str,
    ) -> list[PromptCandidate]:
        sanitized_text, sanitizers = self._sanitize_prompt(raw_prompt, current_prompt.text)
        variants = [
            ("compact", self._truncate_prompt(sanitized_text, max_lines=6, max_chars=280)),
            ("balanced", self._truncate_prompt(sanitized_text, max_lines=9, max_chars=480)),
            ("guarded", self._guarded_prompt_variant(sanitized_text, current_prompt.text)),
        ]
        deduped: list[PromptCandidate] = []
        seen: set[str] = set()
        raw_hash = hashlib.sha1(raw_prompt.encode("utf-8")).hexdigest()[:10]
        target_count = max(3, count)
        for index, (variant_name, variant_text) in enumerate(variants, start=1):
            normalized = variant_text.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(
                PromptCandidate(
                    name=f"PL-R{index}",
                    text=normalized,
                    rationale=rationale,
                    metadata={
                        "source": "prompt_learning_sdk",
                        "variant": variant_name,
                        "sanitizers_applied": ",".join(sanitizers),
                        "raw_prompt_hash": raw_hash,
                    },
                )
            )
            if len(deduped) >= target_count:
                break
        fallback_variants = [
            ("current_prompt", current_prompt.text.strip()),
            ("short_header", "Text Recognition:\nOutput plain text only."),
        ]
        next_index = len(deduped) + 1
        for variant_name, variant_text in fallback_variants:
            normalized = variant_text.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(
                PromptCandidate(
                    name=f"PL-R{next_index}",
                    text=normalized,
                    rationale=rationale,
                    metadata={
                        "source": "prompt_learning_sdk",
                        "variant": variant_name,
                        "sanitizers_applied": ",".join(sanitizers),
                        "raw_prompt_hash": raw_hash,
                    },
                )
            )
            next_index += 1
            if len(deduped) >= target_count:
                break
        if not deduped:
            deduped.append(
                PromptCandidate(
                    name="PL-R1",
                    text=current_prompt.text,
                    rationale=rationale,
                    metadata={
                        "source": "prompt_learning_sdk",
                        "variant": "fallback",
                        "sanitizers_applied": ",".join(sanitizers),
                        "raw_prompt_hash": raw_hash,
                    },
                )
            )
        return deduped

    def _expand_rule_variants(
        self,
        *,
        raw_prompt: str,
        current_prompt: PromptCandidate,
        count: int,
        rationale: str,
        annotations: list[str],
        learning_examples: list[PromptLearningExample],
    ) -> list[PromptCandidate]:
        sanitized_text, sanitizers = self._sanitize_prompt(raw_prompt, current_prompt.text)
        signals = self._collect_rule_signals(
            sanitized_text=sanitized_text,
            annotations=annotations,
            learning_examples=learning_examples,
        )
        bundles = self._rule_bundles(signals, current_prompt.text)
        deduped: list[PromptCandidate] = []
        seen: set[str] = set()
        raw_hash = hashlib.sha1(raw_prompt.encode("utf-8")).hexdigest()[:10]
        target_count = max(6, count)
        for index, (bundle_name, bundle_rules) in enumerate(bundles[:target_count], start=1):
            rendered = self._render_prompt_from_rule_bundle(bundle_rules)
            normalized = rendered.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(
                PromptCandidate(
                    name=f"PL-R{index}",
                    text=normalized,
                    rationale=rationale,
                    metadata={
                        "source": "prompt_learning_sdk",
                        "variant": bundle_name,
                        "sanitizers_applied": ",".join(sanitizers),
                        "raw_prompt_hash": raw_hash,
                        "rules": ",".join(bundle_rules),
                    },
                )
            )
        if not deduped:
            return self._expand_legacy_variants(
                raw_prompt=raw_prompt,
                current_prompt=current_prompt,
                count=count,
                rationale=rationale,
            )
        return deduped

    def _sanitize_prompt(self, raw_prompt: str, current_prompt_text: str) -> tuple[str, list[str]]:
        text = raw_prompt.replace("\r\n", "\n").strip()
        applied: list[str] = []

        new_text = re.sub(r"^\s*YOUR NEW PROMPT:\s*", "", text, flags=re.IGNORECASE)
        if new_text != text:
            applied.append("remove_scaffolding_header")
            text = new_text.strip()

        new_text = re.sub(r"```(?:[a-zA-Z0-9_-]+)?", "", text)
        if new_text != text:
            applied.append("remove_markdown_fences")
            text = new_text

        lines = [line.strip() for line in text.splitlines()]
        filtered: list[str] = []
        dropped_examples = False
        for line in lines:
            if not line:
                continue
            lower = line.lower()
            if "[data sample]" in lower or "example 1:" in lower or "example 2:" in lower:
                dropped_examples = True
                continue
            if "output examples" in lower or "for reference only" in lower:
                dropped_examples = True
                continue
            filtered.append(line)
        if dropped_examples:
            applied.append("remove_examples")

        deduped: list[str] = []
        seen_lines: set[str] = set()
        for line in filtered:
            normalized = re.sub(r"\s+", " ", line).strip().lower()
            if normalized in seen_lines:
                continue
            seen_lines.add(normalized)
            deduped.append(line)
        if len(deduped) != len(filtered):
            applied.append("dedupe_lines")

        if not deduped or not deduped[0].startswith("Text Recognition:"):
            deduped.insert(0, "Text Recognition:")
            applied.append("add_prompt_header")

        text = "\n".join(deduped).strip()
        if len(text) > 700:
            text = self._truncate_prompt(text, max_lines=12, max_chars=700)
            applied.append("clamp_length")
        if not text:
            text = current_prompt_text
            applied.append("fallback_to_current")
        return text, applied

    def _collect_rule_signals(
        self,
        *,
        sanitized_text: str,
        annotations: list[str],
        learning_examples: list[PromptLearningExample],
    ) -> set[str]:
        combined = "\n".join([sanitized_text, *annotations]).lower()
        tags = list(
            itertools.chain.from_iterable(example.error_tags for example in learning_examples if example.evaluator_correctness == "fail")
        )
        signals: set[str] = {"exact_visible_text", "plain_text_only"}
        if "translate" in combined or "script_substitution" in tags:
            signals.add("no_translation")
            signals.add("preserve_script")
        if "repeat" in combined or "repetition" in tags:
            signals.add("no_repetition")
        if "line" in combined or any(example.metadata.get("line_break_error") == "true" for example in learning_examples):
            signals.add("preserve_line_breaks")
        if "guess" in combined or "missing_content" in tags:
            signals.add("no_guessing")
        if "numeric" in combined or any(example.metadata.get("digit_heavy") == "true" for example in learning_examples):
            signals.add("numeric_strict")
        if "markdown" in combined or any(example.metadata.get("contains_markdown") == "true" for example in learning_examples):
            signals.add("no_markdown")
        if any(example.metadata.get("instruction_echo") == "true" for example in learning_examples):
            signals.add("no_instruction_echo")
        return signals

    def _rule_bundles(self, signals: set[str], current_prompt_text: str) -> list[tuple[str, list[str]]]:
        bundles: list[tuple[str, list[str]]] = []
        bundles.append(("minimal", ["exact_visible_text", "plain_text_only"]))
        bundles.append(("anti_repeat", ["exact_visible_text", "plain_text_only", "no_repetition", "no_markdown"]))
        bundles.append(("anti_translate", ["exact_visible_text", "plain_text_only", "no_translation", "preserve_script"]))
        bundles.append(("layout_safe", ["exact_visible_text", "plain_text_only", "preserve_line_breaks", "no_guessing"]))
        bundles.append(("numeric_safe", ["exact_visible_text", "plain_text_only", "numeric_strict", "no_guessing"]))
        ordered = [rule for rule in (
            "no_translation",
            "preserve_script",
            "no_repetition",
            "preserve_line_breaks",
            "no_guessing",
            "numeric_strict",
            "no_markdown",
            "no_instruction_echo",
        ) if rule in signals]
        if ordered:
            bundles.append(("signal_full", ["exact_visible_text", "plain_text_only", *ordered]))
        bundles.append(("current_prompt", self._rules_from_existing_prompt(current_prompt_text=current_prompt_text)))
        return bundles

    def _rules_from_existing_prompt(self, current_prompt_text: str) -> list[str]:
        text = current_prompt_text.lower()
        rules = ["exact_visible_text", "plain_text_only"]
        if "translate" in text:
            rules.append("no_translation")
        if "repeat" in text:
            rules.append("no_repetition")
        if "line break" in text or "reading order" in text:
            rules.append("preserve_line_breaks")
        if "guess" in text:
            rules.append("no_guessing")
        if "korean" in text or "script" in text or "chinese" in text:
            rules.append("preserve_script")
        return rules

    def _render_prompt_from_rule_bundle(self, rules: list[str]) -> str:
        rule_map = {
            "exact_visible_text": "Transcribe only the visible text exactly as it appears.",
            "plain_text_only": "Output plain text only.",
            "no_translation": "Do not translate, normalize, or correct the text.",
            "preserve_script": "Do not substitute Korean text with Chinese characters or other scripts.",
            "no_repetition": "Do not repeat text.",
            "preserve_line_breaks": "Preserve reading order and line breaks when they are visually clear.",
            "no_guessing": "If text is unclear, keep only the visible portion and do not guess missing characters.",
            "numeric_strict": "For prices, quantities, dates, and codes, copy visible digits and separators only.",
            "no_markdown": "Do not include markdown, labels, or code fences.",
            "no_instruction_echo": "Do not repeat the instruction text in the output.",
        }
        rendered = ["Text Recognition:"]
        seen: set[str] = set()
        for rule in rules:
            line = rule_map.get(rule)
            if not line or line in seen:
                continue
            seen.add(line)
            rendered.append(line)
        return "\n".join(rendered).strip()

    def _truncate_prompt(self, text: str, *, max_lines: int, max_chars: int) -> str:
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        kept = lines[:max_lines]
        result = "\n".join(kept).strip()
        if len(result) > max_chars:
            result = result[:max_chars].rstrip()
        return result

    def _guarded_prompt_variant(self, sanitized_text: str, current_prompt_text: str) -> str:
        lines = [line.strip() for line in sanitized_text.splitlines() if line.strip()]
        rules = [line for line in lines[1:] if line.lower() != "text recognition:"]
        essential = [
            "Transcribe only the visible text.",
            "Output plain text only.",
            "Do not translate, explain, normalize, or guess.",
            "Do not repeat text or include markdown.",
        ]
        merged: list[str] = ["Text Recognition:"]
        seen: set[str] = set()
        for line in essential + rules:
            normalized = line.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            merged.append(line)
            if len(merged) >= 6:
                break
        result = "\n".join(merged).strip()
        return result or current_prompt_text

    def _extract_prompt_text(self, optimized_prompt: PromptVersion | list[dict[str, str]] | str) -> str:
        if isinstance(optimized_prompt, PromptVersion):
            template = optimized_prompt._template
            messages = template.get("messages", []) if isinstance(template, dict) else []
            for message in messages:
                if message.get("role") == "system":
                    return str(message.get("content", "")).strip()
            return ""
        if isinstance(optimized_prompt, list):
            for message in optimized_prompt:
                if message.get("role") == "system":
                    return str(message.get("content", "")).strip()
            return ""
        return optimized_prompt.strip()

    def _build_learning_examples_from_failures(
        self,
        *,
        current_prompt: PromptCandidate,
        failures: list[EvaluationResult],
    ) -> list[PromptLearningExample]:
        examples: list[PromptLearningExample] = []
        for row in failures[:12]:
            examples.append(
                PromptLearningExample(
                    sample_id=row.sample_id,
                    prompt_name=current_prompt.name,
                    current_prompt=current_prompt.text,
                    reference_text=row.reference_text,
                    predicted_text=row.predicted_text,
                    evaluator_correctness="fail",
                    evaluator_explanation=self._feedback_explanation(row),
                    error_tags=self._error_tags(row),
                    raw_cer=row.raw_cer,
                    cer=row.cer,
                    token_f1=row.token_f1,
                    total_score=row.total_score,
                    split=row.split,
                    metadata=self._feedback_metadata(row),
                )
            )
        return examples

    def _feedback_explanation(self, row: EvaluationResult) -> str:
        tags = self._error_tags(row)
        if not tags:
            return "The output should follow exact visible-text transcription more closely."
        field_risk = self._field_risk(row)
        fixes = self._suggested_instruction_change(row, tags)
        return f"Observed issues in a {field_risk} field: {', '.join(tags)}. Recommended prompt change: {fixes}."

    def _error_tags(self, row: EvaluationResult) -> list[str]:
        tags: list[str] = []
        if row.penalties.chinese_mixed > 0:
            tags.append("script_substitution")
        if row.penalties.repetition > 0:
            tags.append("repetition")
        if row.cer >= 0.5:
            tags.append("high_cer")
        if row.token_f1 <= 0.4:
            tags.append("missing_content")
        if row.reference_text and len(row.predicted_text) > len(row.reference_text) * 1.5:
            tags.append("overlong_output")
        return tags

    def _feedback_metadata(self, row: EvaluationResult) -> dict[str, str]:
        reference_length = max(len(row.reference_text), 1)
        predicted_length = len(row.predicted_text)
        return {
            "output_length_ratio": f"{predicted_length / reference_length:.2f}",
            "contains_markdown": str("```" in row.predicted_text or "`" in row.predicted_text).lower(),
            "instruction_echo": str(self._contains_instruction_echo(row.predicted_text)).lower(),
            "field_type_hint": self._field_type_hint(row.reference_text),
            "digit_heavy": str(self._digit_ratio(row.reference_text) >= 0.5).lower(),
            "line_break_error": str(row.reference_text.count("\n") != row.predicted_text.count("\n")).lower(),
            "failure_mode_summary": ", ".join(self._error_tags(row)),
            "suggested_instruction_change": self._suggested_instruction_change(row, self._error_tags(row)),
            "field_risk": self._field_risk(row),
        }

    def _suggested_instruction_change(self, row: EvaluationResult, tags: list[str]) -> str:
        changes: list[str] = []
        if "repetition" in tags:
            changes.append("strengthen the no-repeat rule")
        if "script_substitution" in tags:
            changes.append("forbid script substitution and translation")
        if "overlong_output" in tags:
            changes.append("require plain text only with no markdown or extra labels")
        if row.reference_text.count("\n") != row.predicted_text.count("\n"):
            changes.append("preserve line breaks when visually clear")
        if self._digit_ratio(row.reference_text) >= 0.5:
            changes.append("copy digits and separators exactly without guessing")
        if not changes:
            changes.append("tighten exact visible-text transcription")
        return "; ".join(dict.fromkeys(changes))

    def _field_risk(self, row: EvaluationResult) -> str:
        hint = self._field_type_hint(row.reference_text)
        if hint == "numeric":
            return "numeric"
        if hint in {"date", "address", "mixed"}:
            return hint
        return "general"

    def _contains_instruction_echo(self, text: str) -> bool:
        lowered = text.lower()
        markers = [
            "transcribe",
            "output only",
            "do not include",
            "text recognition",
        ]
        return any(marker in lowered for marker in markers)

    def _field_type_hint(self, text: str) -> str:
        if "." in text and any(char.isdigit() for char in text):
            return "date"
        if any(char.isdigit() for char in text) and any(char.isalpha() for char in text):
            return "mixed"
        if any(char.isdigit() for char in text):
            return "numeric"
        if any(char in text for char in ("동", "로", "길", "번")):
            return "address"
        return "general"

    def _digit_ratio(self, text: str) -> float:
        if not text:
            return 0.0
        digits = sum(char.isdigit() for char in text)
        return digits / len(text)
