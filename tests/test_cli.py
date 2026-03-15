from __future__ import annotations

import sys
from pathlib import Path

import pytest

from glm_ocr_prompt_optimization import cli
from glm_ocr_prompt_optimization.config import Settings
from glm_ocr_prompt_optimization.models import AggregateEvaluation, PromptCandidate

pytestmark = pytest.mark.integration


def _settings(tmp_path: Path) -> Settings:
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


def _aggregate(name: str, text: str, cer: float, score: float) -> AggregateEvaluation:
    return AggregateEvaluation(
        prompt_name=name,
        prompt_text=text,
        sample_count=2,
        mean_raw_cer=cer,
        mean_cer=cer,
        mean_token_f1=1.0 - min(cer, 1.0),
        mean_base_score=score,
        mean_total_score=score,
        non_korean_rate=0.0,
        repetition_rate=0.0,
        empty_rate=0.0,
    )


def test_validate_command_reads_prompt_files_and_formats_output(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "val.jsonl"
    manifest.write_text("", encoding="utf-8")
    baseline_prompt = tmp_path / "baseline.txt"
    final_prompt = tmp_path / "final.txt"
    baseline_prompt.write_text("Text Recognition:", encoding="utf-8")
    final_prompt.write_text("Optimized prompt", encoding="utf-8")
    seen: dict[str, object] = {}

    class FakeRunner:
        def validate(self, *, manifest_path: Path, output_dir: Path, prompts: list[PromptCandidate]):
            seen["manifest_path"] = manifest_path
            seen["output_dir"] = output_dir
            seen["prompts"] = prompts
            return [
                _aggregate("baseline", prompts[0].text, 0.32, 0.68),
                _aggregate("final", prompts[1].text, 0.28, 0.72),
            ]

    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls: _settings(tmp_path)))
    monkeypatch.setattr(cli, "ExperimentRunner", lambda settings: FakeRunner())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "glm-ocr-opt",
            "validate",
            "--manifest",
            str(manifest),
            "--output-dir",
            str(tmp_path / "validation"),
            "--baseline-prompt-file",
            str(baseline_prompt),
            "--final-prompt-file",
            str(final_prompt),
        ],
    )

    cli.main()

    out = capsys.readouterr().out
    assert seen["manifest_path"] == manifest
    prompts = seen["prompts"]
    assert isinstance(prompts, list)
    assert [prompt.text for prompt in prompts] == ["Text Recognition:", "Optimized prompt"]
    assert "baseline: cer=0.3200" in out
    assert "final: cer=0.2800" in out


def test_run_all_writes_adopted_prompt_and_report(tmp_path: Path, monkeypatch, capsys) -> None:
    dev_manifest = tmp_path / "dev.jsonl"
    val_manifest = tmp_path / "val.jsonl"
    dev_manifest.write_text("", encoding="utf-8")
    val_manifest.write_text("", encoding="utf-8")
    seen: dict[str, object] = {}

    class FakeRunner:
        def run_seed_evaluation(self, *, manifest_path: Path, output_dir: Path):
            seen["seed_manifest"] = manifest_path
            seen["seed_output_dir"] = output_dir
            return [_aggregate("P1", "Text Recognition:", 0.25, 0.75)], PromptCandidate(
                name="P1",
                text="Text Recognition:",
            )

        def optimize(self, *, manifest_path: Path, output_dir: Path, starting_prompt: PromptCandidate, rounds: int = 3, candidates_per_round: int = 5):
            seen["optimize_manifest"] = manifest_path
            seen["optimize_output_dir"] = output_dir
            seen["starting_prompt"] = starting_prompt
            return PromptCandidate(name="final", text="Optimized prompt")

        def validate(self, *, manifest_path: Path, output_dir: Path, prompts: list[PromptCandidate]):
            seen["validate_manifest"] = manifest_path
            seen["validate_output_dir"] = output_dir
            seen["validate_prompts"] = prompts
            return [
                _aggregate("baseline", prompts[0].text, 0.30, 0.70),
                _aggregate("final", prompts[1].text, 0.28, 0.74),
            ]

        def select_adopted_prompt(self, *, baseline_prompt: PromptCandidate, final_prompt: PromptCandidate, baseline_eval: AggregateEvaluation, final_eval: AggregateEvaluation):
            seen["selected"] = (baseline_prompt, final_prompt, baseline_eval, final_eval)
            return final_prompt, "Adopted for test"

        def build_report(self, *, baseline: AggregateEvaluation, final: AggregateEvaluation, adopted_prompt: PromptCandidate, adopted_reason: str, final_evaluations_path: Path, report_path: Path, examples_count: int = 10):
            seen["report_final_evaluations_path"] = final_evaluations_path
            seen["report_path"] = report_path
            report_path.write_text('{"status":"ok"}', encoding="utf-8")
            return report_path

    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls: _settings(tmp_path)))
    monkeypatch.setattr(cli, "ExperimentRunner", lambda settings: FakeRunner())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "glm-ocr-opt",
            "run-all",
            "--dev-manifest",
            str(dev_manifest),
            "--val-manifest",
            str(val_manifest),
            "--output-dir",
            str(tmp_path / "runs" / "smoke"),
        ],
    )

    cli.main()

    out = capsys.readouterr().out
    adopted_path = tmp_path / "runs" / "smoke" / "adopted_prompt.txt"
    report_path = tmp_path / "runs" / "smoke" / "final_report.json"
    assert adopted_path.read_text(encoding="utf-8") == "Optimized prompt"
    assert report_path.exists()
    assert seen["report_final_evaluations_path"] == tmp_path / "runs" / "smoke" / "validation" / "final" / "evaluations.jsonl"
    assert "final: cer=0.2800" in out
    assert "adopted=final" in out
