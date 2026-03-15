from pathlib import Path

import pytest

from glm_ocr_prompt_optimization.config import Settings
from glm_ocr_prompt_optimization.experiment import ExperimentRunner
from glm_ocr_prompt_optimization.models import AggregateEvaluation, EvaluationResult, PenaltyBreakdown, PromptCandidate

pytestmark = pytest.mark.integration


class FakeOCRClient:
    def recognize_text(self, *, image_path: Path, prompt: str) -> str:
        if "Do not repeat" in prompt:
            return "반복 반복 반복 반복 반복 반복 반복 반복 반복 반복"
        if "Do not translate" in prompt or "Transcribe all visible text exactly as it appears" in prompt:
            return "스타벅스 아메리카노 4500"
        return "漢字 abc"

    def recognize_text_with_timing(self, *, image_path: Path, prompt: str):
        return self.recognize_text(image_path=image_path, prompt=prompt), {
            "preprocess_seconds": 0.01,
            "request_seconds": 0.02,
            "attempt_count": 1,
            "total_seconds": 0.03,
        }


class FakeOptimizer:
    def generate_candidates(self, **kwargs):
        return [
            PromptCandidate(
                name="R1",
                text="Text Recognition:\nTranscribe all visible text exactly as it appears.\nDo not translate or guess.",
            ),
            PromptCandidate(name="R2", text="Text Recognition:\nDo not repeat text."),
        ]


class FakeArizeLogger:
    def log_aggregate(self, aggregate: AggregateEvaluation) -> bool:
        return True


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        openai_api_key="test",
        openai_model="gpt-5-nano",
        ocr_base_url="http://localhost:8000/v1",
        ocr_api_key="EMPTY",
        ocr_model="GLM-OCR",
        arize_api_key=None,
        arize_space_id=None,
        output_root=tmp_path / "runs",
    )


def _write_manifest(tmp_path: Path) -> Path:
    image = tmp_path / "sample.png"
    image.write_bytes(b"fake")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        '{"id":"s1","image_path":"sample.png","reference_text":"스타벅스 아메리카노 4500","split":"dev","metadata":{}}\n',
        encoding="utf-8",
    )
    return manifest


def test_seed_evaluation_picks_best_prompt(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    runner.ocr_client = FakeOCRClient()
    runner.arize_logger = FakeArizeLogger()

    rows, best_prompt = runner.run_seed_evaluation(
        manifest_path=_write_manifest(tmp_path),
        output_dir=tmp_path / "seed",
    )

    assert len(rows) == 4
    assert best_prompt.name in {"P1", "P2", "P3"}
    assert any("Chinese characters" in row.prompt_text or row.prompt_name == "P1" for row in rows)
    assert (tmp_path / "seed" / "timing_summary.csv").exists()
    assert (tmp_path / "seed" / "P0" / "timings.jsonl").exists()


def test_optimize_writes_final_prompt(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    runner.ocr_client = FakeOCRClient()
    runner.optimizer = FakeOptimizer()
    runner.arize_logger = FakeArizeLogger()
    manifest = _write_manifest(tmp_path)

    final_prompt = runner.optimize(
        manifest_path=manifest,
        output_dir=tmp_path / "optimize",
        starting_prompt=PromptCandidate(name="START", text="Text Recognition:"),
        rounds=1,
        candidates_per_round=2,
    )

    assert "Do not translate" in final_prompt.text
    assert (tmp_path / "optimize" / "final_prompt.txt").exists()
    assert (tmp_path / "optimize" / "timing_summary.csv").exists()
    assert (tmp_path / "optimize" / "round_01" / "timings.jsonl").exists()


def test_build_report_creates_json(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    evaluation_path = tmp_path / "evaluations.jsonl"
    evaluation_path.write_text(
        (
            '{"sample_id":"s1","prompt_name":"final","raw_cer":0.1,"cer":0.1,"token_f1":1.0,"base_score":0.9,"total_score":0.9,'
            '"penalties":{"chinese_mixed":0.0,"repetition":0.0},'
            '"predicted_text":"합계 12000","reference_text":"합계 12000","image_path":"sample.png","split":"val"}\n'
        ),
        encoding="utf-8",
    )

    baseline = AggregateEvaluation(
        prompt_name="baseline",
        prompt_text="Text Recognition:",
        sample_count=1,
        mean_raw_cer=0.5,
        mean_cer=0.5,
        mean_token_f1=0.5,
        mean_base_score=0.5,
        mean_total_score=0.4,
        chinese_rate=0.5,
        repetition_rate=0.5,
    )
    final = AggregateEvaluation(
        prompt_name="final",
        prompt_text="optimized",
        sample_count=1,
        mean_raw_cer=0.1,
        mean_cer=0.1,
        mean_token_f1=1.0,
        mean_base_score=0.9,
        mean_total_score=0.9,
        chinese_rate=0.0,
        repetition_rate=0.0,
    )

    report_path = runner.build_report(
        baseline=baseline,
        final=final,
        adopted_prompt=PromptCandidate(name="baseline", text="Text Recognition:"),
        adopted_reason="validation fallback",
        final_evaluations_path=evaluation_path,
        report_path=tmp_path / "report.json",
    )

    assert report_path.exists()


def test_select_adopted_prompt_falls_back_to_baseline_when_final_is_worse(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    baseline_prompt = PromptCandidate(name="baseline", text="Text Recognition:")
    final_prompt = PromptCandidate(name="final", text="long optimized prompt")
    baseline = AggregateEvaluation(
        prompt_name="baseline",
        prompt_text=baseline_prompt.text,
        sample_count=100,
        mean_raw_cer=0.3,
        mean_cer=0.3,
        mean_token_f1=0.8,
        mean_base_score=0.7,
        mean_total_score=0.69,
        chinese_rate=0.01,
        repetition_rate=0.0,
    )
    final = AggregateEvaluation(
        prompt_name="final",
        prompt_text=final_prompt.text,
        sample_count=100,
        mean_raw_cer=0.6,
        mean_cer=0.6,
        mean_token_f1=0.4,
        mean_base_score=0.4,
        mean_total_score=0.39,
        chinese_rate=0.0,
        repetition_rate=0.0,
    )

    adopted, reason = runner.select_adopted_prompt(
        baseline_prompt=baseline_prompt,
        final_prompt=final_prompt,
        baseline_eval=baseline,
        final_eval=final,
    )

    assert adopted.name == "baseline"
    assert "Rejected optimized prompt" in reason


def test_select_adopted_prompt_adopts_final_when_cer_improves_even_without_stability_gain(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    baseline_prompt = PromptCandidate(name="baseline", text="Text Recognition:")
    final_prompt = PromptCandidate(name="final", text="optimized")
    baseline = AggregateEvaluation(
        prompt_name="baseline",
        prompt_text=baseline_prompt.text,
        sample_count=100,
        mean_raw_cer=0.3,
        mean_cer=0.3,
        mean_token_f1=0.8,
        mean_base_score=0.7,
        mean_total_score=0.72,
        chinese_rate=0.0,
        repetition_rate=0.0,
    )
    final = AggregateEvaluation(
        prompt_name="final",
        prompt_text=final_prompt.text,
        sample_count=100,
        mean_raw_cer=0.2,
        mean_cer=0.2,
        mean_token_f1=0.75,
        mean_base_score=0.76,
        mean_total_score=0.70,
        chinese_rate=0.05,
        repetition_rate=0.05,
    )

    adopted, reason = runner.select_adopted_prompt(
        baseline_prompt=baseline_prompt,
        final_prompt=final_prompt,
        baseline_eval=baseline,
        final_eval=final,
    )

    assert adopted.name == "final"
    assert reason == "Adopted optimized prompt because CER improved on validation."


def test_select_adopted_prompt_allows_prompts_up_to_1024_chars(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    baseline_prompt = PromptCandidate(name="baseline", text="Text Recognition:")
    final_prompt = PromptCandidate(name="final", text="x" * 1024)
    baseline = AggregateEvaluation(
        prompt_name="baseline",
        prompt_text=baseline_prompt.text,
        sample_count=1,
        mean_raw_cer=0.3,
        mean_cer=0.3,
        mean_token_f1=0.8,
        mean_base_score=0.7,
        mean_total_score=0.7,
        chinese_rate=0.0,
        repetition_rate=0.0,
    )
    final = AggregateEvaluation(
        prompt_name="final",
        prompt_text=final_prompt.text,
        sample_count=1,
        mean_raw_cer=0.2,
        mean_cer=0.2,
        mean_token_f1=0.85,
        mean_base_score=0.8,
        mean_total_score=0.8,
        chinese_rate=0.0,
        repetition_rate=0.0,
    )

    adopted, _ = runner.select_adopted_prompt(
        baseline_prompt=baseline_prompt,
        final_prompt=final_prompt,
        baseline_eval=baseline,
        final_eval=final,
    )

    assert adopted.name == "final"
