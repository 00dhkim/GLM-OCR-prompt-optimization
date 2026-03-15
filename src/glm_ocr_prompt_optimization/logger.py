from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import AggregateEvaluation, EvaluationResult, OCRResult, PromptCandidate, TimingRecord


class ExperimentLogger:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_predictions(self, rows: Iterable[OCRResult], filename: str = "predictions.jsonl") -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                payload = asdict(row)
                payload["image_path"] = str(row.image_path)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path

    def write_evaluations(self, rows: Iterable[EvaluationResult], filename: str = "evaluations.jsonl") -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                payload = asdict(row)
                payload["image_path"] = str(row.image_path)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path

    def write_aggregate_csv(self, rows: Iterable[AggregateEvaluation], filename: str = "aggregate.csv") -> Path:
        path = self.output_dir / filename
        fieldnames = list(AggregateEvaluation.__dataclass_fields__.keys())
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))
        return path

    def write_prompt_file(self, prompt: PromptCandidate, filename: str = "final_prompt.txt") -> Path:
        path = self.output_dir / filename
        path.write_text(prompt.text, encoding="utf-8")
        return path

    def write_prompt_catalog(self, prompts: Iterable[PromptCandidate], filename: str = "prompt_candidates.jsonl") -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            for prompt in prompts:
                handle.write(json.dumps(asdict(prompt), ensure_ascii=False) + "\n")
        return path

    def write_timings(self, rows: Iterable[TimingRecord], filename: str = "timings.jsonl") -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                payload = asdict(row)
                if row.image_path is not None:
                    payload["image_path"] = str(row.image_path)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path

    def write_timing_summary(self, rows: Iterable[TimingRecord], filename: str = "timing_summary.csv") -> Path:
        path = self.output_dir / filename
        fieldnames = list(TimingRecord.__dataclass_fields__.keys())
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                payload = asdict(row)
                if row.image_path is not None:
                    payload["image_path"] = str(row.image_path)
                writer.writerow(payload)
        return path
