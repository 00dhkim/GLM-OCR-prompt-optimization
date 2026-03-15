from __future__ import annotations

import json
import random
import time
from dataclasses import asdict
from pathlib import Path

from .arize_logger import ArizeLogger
from .config import Settings
from .dataset import load_manifest
from .logger import ExperimentLogger
from .metrics import aggregate_evaluations, evaluate_prediction
from .models import AggregateEvaluation, EvaluationResult, OCRResult, PenaltyBreakdown, PromptCandidate, TimingRecord
from .ocr_client import OCRClient
from .optimizer import PromptOptimizer
from .prompts import default_seed_prompts


class ExperimentRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ocr_client = OCRClient(
            base_url=settings.ocr_base_url,
            api_key=settings.ocr_api_key,
            model=settings.ocr_model,
        )
        self.optimizer = (
            PromptOptimizer(api_key=settings.openai_api_key, model=settings.openai_model)
            if settings.openai_api_key
            else None
        )
        self.arize_logger = ArizeLogger(
            api_key=settings.arize_api_key,
            space_id=settings.arize_space_id,
        )

    def prepare_split(
        self,
        *,
        source_manifest: Path,
        output_dir: Path,
        dev_count: int = 60,
        val_count: int = 100,
        seed: int = 42,
    ) -> tuple[Path, Path]:
        items = load_manifest(source_manifest)
        shuffled = list(items)
        random.Random(seed).shuffle(shuffled)
        dev_items = shuffled[:dev_count]
        val_items = shuffled[dev_count : dev_count + val_count]

        output_dir.mkdir(parents=True, exist_ok=True)
        dev_path = output_dir / "dev.jsonl"
        val_path = output_dir / "val.jsonl"
        self._write_manifest(dev_path, dev_items, split="dev")
        self._write_manifest(val_path, val_items, split="val")
        return dev_path, val_path

    def run_seed_evaluation(self, *, manifest_path: Path, output_dir: Path) -> tuple[list[AggregateEvaluation], PromptCandidate]:
        stage_started_at = time.perf_counter()
        prompts = default_seed_prompts()
        logger = ExperimentLogger(output_dir)
        logger.write_prompt_catalog(prompts, filename="seed_prompts.jsonl")

        aggregate_rows: list[AggregateEvaluation] = []
        timing_rows: list[TimingRecord] = []
        best_prompt = prompts[0]
        best_score = float("-inf")

        for prompt in prompts:
            prompt_started_at = time.perf_counter()
            predictions, evaluations, sample_timings = self._evaluate_manifest(
                manifest_path=manifest_path,
                prompt=prompt,
                stage="seed",
            )
            prompt_dir = output_dir / prompt.name
            prompt_logger = ExperimentLogger(prompt_dir)
            prompt_logger.write_predictions(predictions)
            prompt_logger.write_evaluations(evaluations)
            prompt_logger.write_timings(sample_timings)
            aggregate = aggregate_evaluations(evaluations, prompt.text)
            aggregate_rows.append(aggregate)
            timing_rows.extend(sample_timings)
            timing_rows.append(
                TimingRecord(
                    event_type="prompt_evaluation",
                    stage="seed",
                    prompt_name=prompt.name,
                    total_seconds=time.perf_counter() - prompt_started_at,
                    sample_count=len(sample_timings),
                    preprocess_seconds=sum(row.preprocess_seconds for row in sample_timings),
                    request_seconds=sum(row.request_seconds for row in sample_timings),
                    evaluation_seconds=sum(row.evaluation_seconds for row in sample_timings),
                    attempt_count=sum(row.attempt_count for row in sample_timings),
                )
            )
            if self._is_better_prompt(aggregate, prompt, best_score, best_prompt):
                best_score = aggregate.mean_total_score
                best_prompt = prompt

        logger.write_aggregate_csv(aggregate_rows, filename="seed_aggregate.csv")
        logger.write_prompt_file(best_prompt, filename="best_seed_prompt.txt")
        timing_rows.append(
            TimingRecord(
                event_type="stage_total",
                stage="seed",
                total_seconds=time.perf_counter() - stage_started_at,
                sample_count=sum(row.sample_count for row in timing_rows if row.event_type == "prompt_evaluation"),
                preprocess_seconds=sum(row.preprocess_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                request_seconds=sum(row.request_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                evaluation_seconds=sum(row.evaluation_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                attempt_count=sum(row.attempt_count for row in timing_rows if row.event_type == "prompt_evaluation"),
            )
        )
        logger.write_timing_summary(timing_rows, filename="timing_summary.csv")
        self._log_arize_many(aggregate_rows)
        return aggregate_rows, best_prompt

    def optimize(
        self,
        *,
        manifest_path: Path,
        output_dir: Path,
        starting_prompt: PromptCandidate | None = None,
        rounds: int = 3,
        candidates_per_round: int = 5,
    ) -> PromptCandidate:
        if self.optimizer is None:
            raise RuntimeError("OPENAI_API_KEY is required for optimization.")

        stage_started_at = time.perf_counter()
        logger = ExperimentLogger(output_dir)
        current_prompt = starting_prompt or default_seed_prompts()[0]
        all_aggregates: list[AggregateEvaluation] = []
        all_candidates: list[PromptCandidate] = [current_prompt]
        timing_rows: list[TimingRecord] = []

        for round_index in range(1, rounds + 1):
            prompt_started_at = time.perf_counter()
            predictions, evaluations, sample_timings = self._evaluate_manifest(
                manifest_path=manifest_path,
                prompt=current_prompt,
                stage="optimize",
                round_index=round_index,
            )
            aggregate = aggregate_evaluations(evaluations, current_prompt.text)
            round_dir = output_dir / f"round_{round_index:02d}"
            round_logger = ExperimentLogger(round_dir)
            round_logger.write_predictions(predictions)
            round_logger.write_evaluations(evaluations)
            round_logger.write_timings(sample_timings)
            timing_rows.extend(sample_timings)
            timing_rows.append(
                TimingRecord(
                    event_type="prompt_evaluation",
                    stage="optimize",
                    round_index=round_index,
                    prompt_name=current_prompt.name,
                    total_seconds=time.perf_counter() - prompt_started_at,
                    sample_count=len(sample_timings),
                    preprocess_seconds=sum(row.preprocess_seconds for row in sample_timings),
                    request_seconds=sum(row.request_seconds for row in sample_timings),
                    evaluation_seconds=sum(row.evaluation_seconds for row in sample_timings),
                    attempt_count=sum(row.attempt_count for row in sample_timings),
                )
            )

            sorted_failures = sorted(
                evaluations,
                key=lambda row: (row.total_score, -row.cer),
            )
            failure_cases = sorted_failures[:15]

            generated = self.optimizer.generate_candidates(
                current_prompt=current_prompt,
                aggregate=aggregate,
                failures=failure_cases,
                count=candidates_per_round,
            )
            round_logger.write_prompt_catalog(generated, filename="generated_candidates.jsonl")
            candidate_aggregates, winner = self._evaluate_candidates(
                manifest_path=manifest_path,
                output_dir=round_dir / "candidates",
                candidates=generated,
                stage="optimize",
                round_index=round_index,
                timing_rows=timing_rows,
            )
            current_prompt = winner
            all_candidates.extend(generated)
            all_aggregates.append(aggregate)
            all_aggregates.extend(candidate_aggregates)
            self._append_failure_report(round_dir / "failures.jsonl", failure_cases)
            self._log_arize_many([aggregate, *candidate_aggregates])

        logger.write_aggregate_csv(all_aggregates, filename="optimization_aggregate.csv")
        logger.write_prompt_catalog(all_candidates, filename="all_candidates.jsonl")
        logger.write_prompt_file(current_prompt, filename="final_prompt.txt")
        timing_rows.append(
            TimingRecord(
                event_type="stage_total",
                stage="optimize",
                total_seconds=time.perf_counter() - stage_started_at,
                sample_count=sum(row.sample_count for row in timing_rows if row.event_type == "prompt_evaluation"),
                preprocess_seconds=sum(row.preprocess_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                request_seconds=sum(row.request_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                evaluation_seconds=sum(row.evaluation_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                attempt_count=sum(row.attempt_count for row in timing_rows if row.event_type == "prompt_evaluation"),
            )
        )
        logger.write_timing_summary(timing_rows, filename="timing_summary.csv")
        return current_prompt

    def validate(
        self,
        *,
        manifest_path: Path,
        output_dir: Path,
        prompts: list[PromptCandidate],
    ) -> list[AggregateEvaluation]:
        stage_started_at = time.perf_counter()
        logger = ExperimentLogger(output_dir)
        aggregate_rows: list[AggregateEvaluation] = []
        timing_rows: list[TimingRecord] = []
        for prompt in prompts:
            prompt_started_at = time.perf_counter()
            predictions, evaluations, sample_timings = self._evaluate_manifest(
                manifest_path=manifest_path,
                prompt=prompt,
                stage="validation",
            )
            prompt_dir = output_dir / prompt.name
            prompt_logger = ExperimentLogger(prompt_dir)
            prompt_logger.write_predictions(predictions)
            prompt_logger.write_evaluations(evaluations)
            prompt_logger.write_timings(sample_timings)
            aggregate_rows.append(aggregate_evaluations(evaluations, prompt.text))
            timing_rows.extend(sample_timings)
            timing_rows.append(
                TimingRecord(
                    event_type="prompt_evaluation",
                    stage="validation",
                    prompt_name=prompt.name,
                    total_seconds=time.perf_counter() - prompt_started_at,
                    sample_count=len(sample_timings),
                    preprocess_seconds=sum(row.preprocess_seconds for row in sample_timings),
                    request_seconds=sum(row.request_seconds for row in sample_timings),
                    evaluation_seconds=sum(row.evaluation_seconds for row in sample_timings),
                    attempt_count=sum(row.attempt_count for row in sample_timings),
                )
            )
        logger.write_aggregate_csv(aggregate_rows, filename="validation_aggregate.csv")
        timing_rows.append(
            TimingRecord(
                event_type="stage_total",
                stage="validation",
                total_seconds=time.perf_counter() - stage_started_at,
                sample_count=sum(row.sample_count for row in timing_rows if row.event_type == "prompt_evaluation"),
                preprocess_seconds=sum(row.preprocess_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                request_seconds=sum(row.request_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                evaluation_seconds=sum(row.evaluation_seconds for row in timing_rows if row.event_type == "prompt_evaluation"),
                attempt_count=sum(row.attempt_count for row in timing_rows if row.event_type == "prompt_evaluation"),
            )
        )
        logger.write_timing_summary(timing_rows, filename="timing_summary.csv")
        self._log_arize_many(aggregate_rows)
        return aggregate_rows

    def build_report(
        self,
        *,
        baseline: AggregateEvaluation,
        final: AggregateEvaluation,
        adopted_prompt: PromptCandidate,
        adopted_reason: str,
        final_evaluations_path: Path,
        report_path: Path,
        examples_count: int = 10,
    ) -> Path:
        evaluations = self._load_evaluations(final_evaluations_path)
        improved_examples = sorted(
            evaluations,
            key=lambda row: (row.total_score, -row.cer),
            reverse=True,
        )[:examples_count]

        report = {
            "baseline": asdict(baseline),
            "final": asdict(final),
            "relative_cer_improvement": (
                (baseline.mean_cer - final.mean_cer) / baseline.mean_cer if baseline.mean_cer else 0.0
            ),
            "stability_improvements": {
                "chinese_rate_delta": baseline.chinese_rate - final.chinese_rate,
                "repetition_rate_delta": baseline.repetition_rate - final.repetition_rate,
            },
            "adopted_prompt": {
                "name": adopted_prompt.name,
                "text": adopted_prompt.text,
                "reason": adopted_reason,
            },
            "examples": [self._serialize_evaluation(row) for row in improved_examples],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report_path

    def select_adopted_prompt(
        self,
        *,
        baseline_prompt: PromptCandidate,
        final_prompt: PromptCandidate,
        baseline_eval: AggregateEvaluation,
        final_eval: AggregateEvaluation,
        max_prompt_length: int = 1024,
        tie_margin: float = 0.01,
    ) -> tuple[PromptCandidate, str]:
        if len(final_prompt.text) > max_prompt_length:
            return baseline_prompt, "Rejected optimized prompt because it exceeded the prompt length limit."

        cer_improved = final_eval.mean_cer < baseline_eval.mean_cer
        if cer_improved:
            return final_prompt, "Adopted optimized prompt because CER improved on validation."

        score_gap = abs(final_eval.mean_total_score - baseline_eval.mean_total_score)
        if score_gap <= tie_margin:
            shorter = final_prompt if len(final_prompt.text) < len(baseline_prompt.text) else baseline_prompt
            return shorter, "Scores were effectively tied, so the shorter prompt was adopted."

        return baseline_prompt, "Rejected optimized prompt because it did not satisfy the PRD adoption rules on validation."

    def _evaluate_candidates(
        self,
        *,
        manifest_path: Path,
        output_dir: Path,
        candidates: list[PromptCandidate],
        stage: str,
        round_index: int | None = None,
        timing_rows: list[TimingRecord] | None = None,
    ) -> tuple[list[AggregateEvaluation], PromptCandidate]:
        aggregate_rows: list[AggregateEvaluation] = []
        best_prompt = candidates[0]
        best_score = float("-inf")
        for prompt in candidates:
            prompt_started_at = time.perf_counter()
            predictions, evaluations, sample_timings = self._evaluate_manifest(
                manifest_path=manifest_path,
                prompt=prompt,
                stage=stage,
                round_index=round_index,
            )
            prompt_dir = output_dir / prompt.name
            prompt_logger = ExperimentLogger(prompt_dir)
            prompt_logger.write_predictions(predictions)
            prompt_logger.write_evaluations(evaluations)
            prompt_logger.write_timings(sample_timings)
            aggregate = aggregate_evaluations(evaluations, prompt.text)
            aggregate_rows.append(aggregate)
            if timing_rows is not None:
                timing_rows.extend(sample_timings)
                timing_rows.append(
                    TimingRecord(
                        event_type="prompt_evaluation",
                        stage=stage,
                        round_index=round_index,
                        prompt_name=prompt.name,
                        total_seconds=time.perf_counter() - prompt_started_at,
                        sample_count=len(sample_timings),
                        preprocess_seconds=sum(row.preprocess_seconds for row in sample_timings),
                        request_seconds=sum(row.request_seconds for row in sample_timings),
                        evaluation_seconds=sum(row.evaluation_seconds for row in sample_timings),
                        attempt_count=sum(row.attempt_count for row in sample_timings),
                    )
                )
            if self._is_better_prompt(aggregate, prompt, best_score, best_prompt):
                best_score = aggregate.mean_total_score
                best_prompt = prompt
        return aggregate_rows, best_prompt

    def _evaluate_manifest(
        self,
        *,
        manifest_path: Path,
        prompt: PromptCandidate,
        stage: str,
        round_index: int | None = None,
    ) -> tuple[list[OCRResult], list[EvaluationResult], list[TimingRecord]]:
        items = load_manifest(manifest_path)
        predictions: list[OCRResult] = []
        evaluations: list[EvaluationResult] = []
        timings: list[TimingRecord] = []

        for item in items:
            sample_started_at = time.perf_counter()
            ocr_result = self.ocr_client.recognize_text_with_timing if hasattr(self.ocr_client, "recognize_text_with_timing") else None
            if ocr_result is not None:
                predicted_text, ocr_timing = ocr_result(image_path=item.image_path, prompt=prompt.text)
            else:
                predicted_text = self.ocr_client.recognize_text(image_path=item.image_path, prompt=prompt.text)
                ocr_timing = {
                    "preprocess_seconds": 0.0,
                    "request_seconds": 0.0,
                    "attempt_count": 1,
                    "total_seconds": 0.0,
                }
            prediction = OCRResult(
                sample_id=item.sample_id,
                prompt_name=prompt.name,
                prompt_text=prompt.text,
                predicted_text=predicted_text,
                reference_text=item.reference_text,
                image_path=item.image_path,
                split=item.split,
                metadata=item.metadata,
            )
            predictions.append(prediction)
            evaluation_started_at = time.perf_counter()
            evaluations.append(
                evaluate_prediction(
                    sample_id=item.sample_id,
                    prompt_name=prompt.name,
                    predicted_text=predicted_text,
                    reference_text=item.reference_text,
                    image_path=item.image_path,
                    split=item.split,
                    metadata=item.metadata,
                )
            )
            evaluation_seconds = time.perf_counter() - evaluation_started_at
            timings.append(
                TimingRecord(
                    event_type="sample_evaluation",
                    stage=stage,
                    prompt_name=prompt.name,
                    sample_id=item.sample_id,
                    image_path=item.image_path,
                    split=item.split,
                    round_index=round_index,
                    total_seconds=time.perf_counter() - sample_started_at,
                    preprocess_seconds=float(ocr_timing.get("preprocess_seconds", 0.0)),
                    request_seconds=float(ocr_timing.get("request_seconds", 0.0)),
                    evaluation_seconds=evaluation_seconds,
                    sample_count=1,
                    attempt_count=int(ocr_timing.get("attempt_count", 0)),
                )
            )
        return predictions, evaluations, timings

    def _append_failure_report(self, path: Path, failures: list[EvaluationResult]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in failures:
                handle.write(json.dumps(self._serialize_evaluation(row), ensure_ascii=False) + "\n")

    def _serialize_evaluation(self, row: EvaluationResult) -> dict[str, object]:
        return {
            "sample_id": row.sample_id,
            "prompt_name": row.prompt_name,
            "raw_cer": row.raw_cer,
            "cer": row.cer,
            "token_f1": row.token_f1,
            "base_score": row.base_score,
            "total_score": row.total_score,
            "penalties": {
                "chinese_mixed": row.penalties.chinese_mixed,
                "repetition": row.penalties.repetition,
            },
            "predicted_text": row.predicted_text,
            "reference_text": row.reference_text,
            "image_path": str(row.image_path),
            "split": row.split,
        }

    def _log_arize_many(self, rows: list[AggregateEvaluation]) -> None:
        for row in rows:
            self.arize_logger.log_aggregate(row)

    def _load_evaluations(self, path: Path) -> list[EvaluationResult]:
        rows: list[EvaluationResult] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                penalties = payload["penalties"]
                rows.append(
                    EvaluationResult(
                        sample_id=payload["sample_id"],
                        prompt_name=payload["prompt_name"],
                        raw_cer=payload.get("raw_cer", payload["cer"]),
                        cer=payload["cer"],
                        token_f1=payload.get("token_f1", 0.0),
                        base_score=payload["base_score"],
                        total_score=payload["total_score"],
                        penalties=PenaltyBreakdown(
                            chinese_mixed=penalties["chinese_mixed"],
                            repetition=penalties["repetition"],
                        ),
                        predicted_text=payload["predicted_text"],
                        reference_text=payload["reference_text"],
                        image_path=Path(payload["image_path"]),
                        split=payload.get("split"),
                    )
                )
        return rows

    def _write_manifest(self, path: Path, items, *, split: str) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                payload = {
                    "id": item.sample_id,
                    "image_path": str(item.image_path),
                    "reference_text": item.reference_text,
                    "split": split,
                    "metadata": item.metadata,
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _is_better_prompt(
        self,
        aggregate: AggregateEvaluation,
        prompt: PromptCandidate,
        best_score: float,
        best_prompt: PromptCandidate,
    ) -> bool:
        if aggregate.mean_total_score > best_score:
            return True
        if aggregate.mean_total_score < best_score:
            return False
        return len(prompt.text) < len(best_prompt.text)
