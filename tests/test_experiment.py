from pathlib import Path

from glm_ocr_prompt_optimization.config import Settings
from glm_ocr_prompt_optimization.experiment import ExperimentRunner
from glm_ocr_prompt_optimization.models import AggregateEvaluation, EvaluationResult, PenaltyBreakdown, PromptCandidate


class FakeOCRClient:
    def recognize_text(self, *, image_path: Path, prompt: str) -> str:
        if "반복" in prompt:
            return "반복 반복 반복 반복 반복 반복 반복 반복 반복 반복"
        if "한국어 중심" in prompt:
            return "스타벅스 아메리카노 4500"
        return "漢字 abc"


class FakeOptimizer:
    def generate_candidates(self, **kwargs):
        return [
            PromptCandidate(name="R1", text="Text Recognition:\n보이는 글자를 한국어 중심으로 그대로 전사하라."),
            PromptCandidate(name="R2", text="Text Recognition:\n같은 문자열을 반복 생성하지 마라."),
        ]


class FakeArizeLogger:
    def log_aggregate(self, aggregate: AggregateEvaluation) -> bool:
        return True


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        openai_api_key="test",
        openai_model="gpt-5-nano",
        ollama_base_url="http://localhost:11434/v1",
        ollama_api_key="ollama",
        ollama_model="glm-ocr:latest",
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

    assert "한국어 중심" in final_prompt.text
    assert (tmp_path / "optimize" / "final_prompt.txt").exists()


def test_build_report_creates_json(tmp_path: Path) -> None:
    runner = ExperimentRunner(_build_settings(tmp_path))
    evaluation_path = tmp_path / "evaluations.jsonl"
    evaluation_path.write_text(
        (
            '{"sample_id":"s1","prompt_name":"final","cer":0.1,"base_score":0.9,"total_score":0.9,'
            '"penalties":{"non_korean_mixed":0.0,"repetition":0.0,"empty_or_garbage":0.0},'
            '"predicted_text":"합계 12000","reference_text":"합계 12000","image_path":"sample.png","split":"val"}\n'
        ),
        encoding="utf-8",
    )

    baseline = AggregateEvaluation(
        prompt_name="baseline",
        prompt_text="Text Recognition:",
        sample_count=1,
        mean_cer=0.5,
        mean_base_score=0.5,
        mean_total_score=0.4,
        non_korean_rate=0.5,
        repetition_rate=0.5,
        empty_rate=0.0,
    )
    final = AggregateEvaluation(
        prompt_name="final",
        prompt_text="optimized",
        sample_count=1,
        mean_cer=0.1,
        mean_base_score=0.9,
        mean_total_score=0.9,
        non_korean_rate=0.0,
        repetition_rate=0.0,
        empty_rate=0.0,
    )

    report_path = runner.build_report(
        baseline=baseline,
        final=final,
        final_evaluations_path=evaluation_path,
        report_path=tmp_path / "report.json",
    )

    assert report_path.exists()
