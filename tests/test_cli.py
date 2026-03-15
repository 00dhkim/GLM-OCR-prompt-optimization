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
        ocr_base_url="http://localhost:8000/v1",
        ocr_api_key="EMPTY",
        ocr_model="GLM-OCR",
        arize_api_key=None,
        arize_space_id=None,
        output_root=tmp_path / "runs",
        phoenix_base_url=None,
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
        chinese_rate=0.0,
        repetition_rate=0.0,
        markdown_leakage_rate=0.0,
        instruction_echo_rate=0.0,
        line_break_match_rate=1.0,
        numeric_field_cer=cer,
        non_numeric_field_cer=cer,
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

        def optimize(self, *, manifest_path: Path, output_dir: Path, starting_prompt: PromptCandidate, rounds: int = 3, candidates_per_round: int = 5, candidate_strategy: str = "ocr-rules"):
            seen["optimize_manifest"] = manifest_path
            seen["optimize_output_dir"] = output_dir
            seen["starting_prompt"] = starting_prompt
            seen["rounds"] = rounds
            seen["candidates_per_round"] = candidates_per_round
            seen["candidate_strategy"] = candidate_strategy
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
            "--rounds",
            "1",
            "--candidates-per-round",
            "4",
            "--candidate-strategy",
            "ocr-rules",
        ],
    )

    cli.main()

    out = capsys.readouterr().out
    adopted_path = tmp_path / "runs" / "smoke" / "adopted_prompt.txt"
    report_path = tmp_path / "runs" / "smoke" / "final_report.json"
    assert adopted_path.read_text(encoding="utf-8") == "Optimized prompt"
    assert report_path.exists()
    assert seen["report_final_evaluations_path"] == tmp_path / "runs" / "smoke" / "validation" / "final" / "evaluations.jsonl"
    assert seen["rounds"] == 1
    assert seen["candidates_per_round"] == 4
    assert seen["candidate_strategy"] == "ocr-rules"
    assert "final: cer=0.2800" in out
    assert "adopted=final" in out


def test_prepare_aihub_public_admin_command_builds_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    def fake_build(*, source_dir: Path, output_path: Path, split: str, limit: int | None, seed: int):
        seen["source_dir"] = source_dir
        seen["output_path"] = output_path
        seen["split"] = split
        seen["limit"] = limit
        seen["seed"] = seed
        return [object(), object()]

    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls: _settings(tmp_path)))
    monkeypatch.setattr(cli, "build_aihub_public_admin_manifest", fake_build)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "glm-ocr-opt",
            "prepare-aihub-public-admin",
            "--source-dir",
            str(tmp_path / "aihub"),
            "--output-path",
            str(tmp_path / "manifests" / "train.jsonl"),
            "--split",
            "train",
            "--limit",
            "5",
            "--seed",
            "7",
        ],
    )

    cli.main()

    out = capsys.readouterr().out
    assert seen["split"] == "train"
    assert seen["limit"] == 5
    assert seen["seed"] == 7
    assert "manifest=" in out
    assert "(2 items)" in out


def test_summarize_timings_prints_stage_and_sample_hotspots(tmp_path: Path, monkeypatch, capsys) -> None:
    run_dir = tmp_path / "runs" / "timed"
    seed_dir = run_dir / "seed"
    prompt_dir = seed_dir / "P0"
    prompt_dir.mkdir(parents=True)
    (seed_dir / "timing_summary.csv").write_text(
        (
            "event_type,stage,total_seconds,prompt_name,sample_id,image_path,split,round_index,preprocess_seconds,request_seconds,evaluation_seconds,sample_count,attempt_count\n"
            "prompt_evaluation,seed,12.5,P0,,,,,0.5,11.5,0.5,5,6\n"
            "stage_total,seed,12.5,,,,,,0.5,11.5,0.5,5,6\n"
        ),
        encoding="utf-8",
    )
    (prompt_dir / "timings.jsonl").write_text(
        (
            '{"event_type":"sample_evaluation","stage":"seed","total_seconds":4.2,"prompt_name":"P0","sample_id":"s2","image_path":"b.png","split":"dev","round_index":null,"preprocess_seconds":0.2,"request_seconds":3.8,"evaluation_seconds":0.2,"sample_count":1,"attempt_count":2}\n'
            '{"event_type":"sample_evaluation","stage":"seed","total_seconds":3.1,"prompt_name":"P0","sample_id":"s1","image_path":"a.png","split":"dev","round_index":null,"preprocess_seconds":0.1,"request_seconds":2.8,"evaluation_seconds":0.2,"sample_count":1,"attempt_count":1}\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls: _settings(tmp_path)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "glm-ocr-opt",
            "summarize-timings",
            "--run-dir",
            str(run_dir),
            "--top-k",
            "1",
        ],
    )

    cli.main()

    out = capsys.readouterr().out
    assert "stage totals:" in out
    assert "seed: total=12.50s" in out
    assert "slow prompts:" in out
    assert "seed:P0: total=12.50s" in out
    assert "slow samples:" in out
    assert "seed:P0:s2: total=4.20s" in out
