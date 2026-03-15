from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .dataset import (
    build_aihub_public_admin_manifest,
    build_cord_v2_manifest,
    build_hf_image_text_manifest,
    build_korie_ocr_manifest,
    download_hf_repo_image_sample,
    filter_items_for_benchmark,
    merge_manifests,
    stratified_split_items,
    write_manifest,
)
from .experiment import ExperimentRunner
from .models import AggregateEvaluation, PromptCandidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glm-ocr-opt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    split_parser = subparsers.add_parser("prepare-split")
    split_parser.add_argument("--source-manifest", type=Path, required=True)
    split_parser.add_argument("--output-dir", type=Path, required=True)
    split_parser.add_argument("--dev-count", type=int, default=60)
    split_parser.add_argument("--val-count", type=int, default=100)
    split_parser.add_argument("--seed", type=int, default=42)

    korie_parser = subparsers.add_parser("prepare-korie-ocr")
    korie_parser.add_argument("--train-dir", type=Path, required=True)
    korie_parser.add_argument("--val-dir", type=Path, required=True)
    korie_parser.add_argument("--test-dir", type=Path, required=True)
    korie_parser.add_argument("--output-dir", type=Path, required=True)
    korie_parser.add_argument("--dev-count", type=int, default=60)
    korie_parser.add_argument("--val-count", type=int, default=100)
    korie_parser.add_argument("--seed", type=int, default=42)

    cord_parser = subparsers.add_parser("prepare-cord-v2")
    cord_parser.add_argument("--output-dir", type=Path, required=True)
    cord_parser.add_argument("--train-count", type=int, default=60)
    cord_parser.add_argument("--val-count", type=int, default=100)
    cord_parser.add_argument("--batch-size", type=int, default=20)

    hf_text_parser = subparsers.add_parser("prepare-hf-image-text")
    hf_text_parser.add_argument("--dataset-id", required=True)
    hf_text_parser.add_argument("--output-dir", type=Path, required=True)
    hf_text_parser.add_argument("--split", default="train")
    hf_text_parser.add_argument("--config", default="default")
    hf_text_parser.add_argument("--count", type=int, default=20)
    hf_text_parser.add_argument("--batch-size", type=int, default=20)
    hf_text_parser.add_argument("--image-field", required=True)
    hf_text_parser.add_argument("--text-field", required=True)
    hf_text_parser.add_argument("--sample-prefix", required=True)

    hf_image_parser = subparsers.add_parser("collect-hf-images")
    hf_image_parser.add_argument("--dataset-id", required=True)
    hf_image_parser.add_argument("--output-dir", type=Path, required=True)
    hf_image_parser.add_argument("--limit", type=int, default=20)

    aihub_parser = subparsers.add_parser("prepare-aihub-public-admin")
    aihub_parser.add_argument("--source-dir", type=Path, required=True)
    aihub_parser.add_argument("--output-path", type=Path, required=True)
    aihub_parser.add_argument("--split", default="train")
    aihub_parser.add_argument("--limit", type=int)
    aihub_parser.add_argument("--seed", type=int, default=42)

    benchmark_parser = subparsers.add_parser("prepare-heldout-benchmark")
    benchmark_parser.add_argument("--source-manifest", type=Path, action="append", required=True)
    benchmark_parser.add_argument("--output-dir", type=Path, required=True)
    benchmark_parser.add_argument("--dev-count", type=int, default=16)
    benchmark_parser.add_argument("--val-count", type=int, default=16)
    benchmark_parser.add_argument("--seed", type=int, default=42)
    benchmark_parser.add_argument("--max-text-length", type=int)
    benchmark_parser.add_argument("--max-image-width", type=int)
    benchmark_parser.add_argument("--max-aspect-ratio", type=float)

    seed_parser = subparsers.add_parser("seed-eval")
    seed_parser.add_argument("--manifest", type=Path, required=True)
    seed_parser.add_argument("--output-dir", type=Path, required=True)

    optimize_parser = subparsers.add_parser("optimize")
    optimize_parser.add_argument("--manifest", type=Path, required=True)
    optimize_parser.add_argument("--output-dir", type=Path, required=True)
    optimize_parser.add_argument("--start-prompt-file", type=Path)
    optimize_parser.add_argument("--rounds", type=int, default=3)
    optimize_parser.add_argument("--candidates-per-round", type=int, default=5)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--manifest", type=Path, required=True)
    validate_parser.add_argument("--output-dir", type=Path, required=True)
    validate_parser.add_argument("--baseline-prompt-file", type=Path)
    validate_parser.add_argument("--final-prompt-file", type=Path, required=True)

    run_parser = subparsers.add_parser("run-all")
    run_parser.add_argument("--dev-manifest", type=Path, required=True)
    run_parser.add_argument("--val-manifest", type=Path, required=True)
    run_parser.add_argument("--output-dir", type=Path, required=True)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.load()
    runner = ExperimentRunner(settings)

    if args.command == "prepare-split":
        dev_path, val_path = runner.prepare_split(
            source_manifest=args.source_manifest,
            output_dir=args.output_dir,
            dev_count=args.dev_count,
            val_count=args.val_count,
            seed=args.seed,
        )
        print(f"dev={dev_path}")
        print(f"val={val_path}")
        return

    if args.command == "prepare-korie-ocr":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        dev_path = args.output_dir / "dev.jsonl"
        val_path = args.output_dir / "val.jsonl"
        test_path = args.output_dir / "test-full.jsonl"
        dev_items = build_korie_ocr_manifest(
            source_dir=args.train_dir,
            output_path=dev_path,
            split="dev",
            limit=args.dev_count,
            seed=args.seed,
        )
        val_items = build_korie_ocr_manifest(
            source_dir=args.val_dir,
            output_path=val_path,
            split="val",
            limit=args.val_count,
            seed=args.seed,
        )
        build_korie_ocr_manifest(
            source_dir=args.test_dir,
            output_path=test_path,
            split="test",
            limit=None,
            seed=args.seed,
        )
        print(f"dev={dev_path} ({len(dev_items)} items)")
        print(f"val={val_path} ({len(val_items)} items)")
        print(f"test={test_path}")
        return

    if args.command == "prepare-cord-v2":
        train_items, val_items = build_cord_v2_manifest(
            output_dir=args.output_dir,
            train_count=args.train_count,
            validation_count=args.val_count,
            batch_size=args.batch_size,
        )
        print(f"dev={args.output_dir / 'dev.jsonl'} ({len(train_items)} items)")
        print(f"val={args.output_dir / 'val.jsonl'} ({len(val_items)} items)")
        return

    if args.command == "prepare-hf-image-text":
        items = build_hf_image_text_manifest(
            dataset_id=args.dataset_id,
            output_dir=args.output_dir,
            split=args.split,
            config=args.config,
            count=args.count,
            batch_size=args.batch_size,
            image_field=args.image_field,
            text_field=args.text_field,
            sample_prefix=args.sample_prefix,
        )
        print(f"manifest={args.output_dir / f'{args.split}.jsonl'} ({len(items)} items)")
        return

    if args.command == "collect-hf-images":
        paths = download_hf_repo_image_sample(
            dataset_id=args.dataset_id,
            output_dir=args.output_dir,
            limit=args.limit,
        )
        print(f"images={len(paths)}")
        if paths:
            print(paths[0])
        return

    if args.command == "prepare-aihub-public-admin":
        items = build_aihub_public_admin_manifest(
            source_dir=args.source_dir,
            output_path=args.output_path,
            split=args.split,
            limit=args.limit,
            seed=args.seed,
        )
        print(f"manifest={args.output_path} ({len(items)} items)")
        return

    if args.command == "prepare-heldout-benchmark":
        merged = merge_manifests(manifest_paths=args.source_manifest)
        filtered = filter_items_for_benchmark(
            merged,
            max_text_length=args.max_text_length,
            max_image_width=args.max_image_width,
            max_aspect_ratio=args.max_aspect_ratio,
        )
        dev_items, val_items = stratified_split_items(
            filtered,
            dev_count=args.dev_count,
            val_count=args.val_count,
            seed=args.seed,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_manifest(args.output_dir / "full.jsonl", filtered)
        write_manifest(args.output_dir / "dev.jsonl", dev_items, split="dev")
        write_manifest(args.output_dir / "val.jsonl", val_items, split="val")
        print(f"filtered={len(filtered)}")
        print(f"dev={args.output_dir / 'dev.jsonl'} ({len(dev_items)} items)")
        print(f"val={args.output_dir / 'val.jsonl'} ({len(val_items)} items)")
        return

    if args.command == "seed-eval":
        aggregate_rows, best_prompt = runner.run_seed_evaluation(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
        )
        _print_best(best_prompt, aggregate_rows)
        return

    if args.command == "optimize":
        start_prompt = (
            PromptCandidate(name="START", text=args.start_prompt_file.read_text(encoding="utf-8").strip())
            if args.start_prompt_file
            else None
        )
        final_prompt = runner.optimize(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            starting_prompt=start_prompt,
            rounds=args.rounds,
            candidates_per_round=args.candidates_per_round,
        )
        print(final_prompt.text)
        return

    if args.command == "validate":
        baseline_text = (
            args.baseline_prompt_file.read_text(encoding="utf-8").strip()
            if args.baseline_prompt_file
            else "Text Recognition:"
        )
        final_text = args.final_prompt_file.read_text(encoding="utf-8").strip()
        results = runner.validate(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            prompts=[
                PromptCandidate(name="baseline", text=baseline_text),
                PromptCandidate(name="final", text=final_text),
            ],
        )
        for row in results:
            print(_format_aggregate(row))
        return

    if args.command == "run-all":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        seed_rows, best_seed = runner.run_seed_evaluation(
            manifest_path=args.dev_manifest,
            output_dir=args.output_dir / "seed",
        )
        final_prompt = runner.optimize(
            manifest_path=args.dev_manifest,
            output_dir=args.output_dir / "optimize",
            starting_prompt=best_seed,
        )
        validation_rows = runner.validate(
            manifest_path=args.val_manifest,
            output_dir=args.output_dir / "validation",
            prompts=[
                PromptCandidate(name="baseline", text="Text Recognition:"),
                PromptCandidate(name="final", text=final_prompt.text),
            ],
        )
        baseline = _find_prompt(validation_rows, "baseline")
        final = _find_prompt(validation_rows, "final")
        adopted_prompt, adopted_reason = runner.select_adopted_prompt(
            baseline_prompt=PromptCandidate(name="baseline", text="Text Recognition:"),
            final_prompt=PromptCandidate(name="final", text=final_prompt.text),
            baseline_eval=baseline,
            final_eval=final,
        )
        (args.output_dir / "adopted_prompt.txt").write_text(adopted_prompt.text, encoding="utf-8")
        runner.build_report(
            baseline=baseline,
            final=final,
            adopted_prompt=adopted_prompt,
            adopted_reason=adopted_reason,
            final_evaluations_path=args.output_dir / "validation" / "final" / "evaluations.jsonl",
            report_path=args.output_dir / "final_report.json",
        )
        print(_format_aggregate(final))
        print(f"adopted={adopted_prompt.name}")
        return

    parser.error(f"Unknown command: {args.command}")


def _print_best(best_prompt: PromptCandidate, rows: list[AggregateEvaluation]) -> None:
    best_row = _find_prompt(rows, best_prompt.name)
    print(_format_aggregate(best_row))
    print(best_prompt.text)


def _find_prompt(rows: list[AggregateEvaluation], name: str) -> AggregateEvaluation:
    for row in rows:
        if row.prompt_name == name:
            return row
    raise ValueError(f"Prompt not found: {name}")


def _format_aggregate(row: AggregateEvaluation) -> str:
    return (
        f"{row.prompt_name}: cer={row.mean_cer:.4f}, "
        f"score={row.mean_total_score:.4f}, "
        f"non_korean={row.non_korean_rate:.2%}, "
        f"repetition={row.repetition_rate:.2%}, "
        f"empty={row.empty_rate:.2%}"
    )
