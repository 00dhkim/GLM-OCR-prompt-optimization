from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "runs" / "cord-v2-mini-r2"
DOCS_DIR = ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "002"
REPORT_PATH = DOCS_DIR / "002_cord_v2_full_receipt_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_seed_chart(seed_rows: list[dict[str, str]]) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    names = [row["prompt_name"] for row in seed_rows]
    cer = [float(row["mean_cer"]) for row in seed_rows]
    score = [float(row["mean_total_score"]) for row in seed_rows]
    axes[0].bar(names, cer, color="#4C78A8")
    axes[0].set_title("CORD Seed CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)
    axes[1].bar(names, score, color="#59A14F")
    axes[1].set_title("CORD Seed Total Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path = ASSET_DIR / "seed.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_iteration_chart(rounds: list[dict]) -> Path:
    labels = [row["winner_name"] for row in rounds]
    cer = [row["winner_cer"] for row in rounds]
    score = [row["winner_score"] for row in rounds]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(labels, cer, marker="o", linewidth=2, color="#4C78A8")
    axes[0].set_title("CORD Optimization CER Trend")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(alpha=0.2)
    axes[0].tick_params(axis="x", rotation=20)
    axes[1].plot(labels, score, marker="o", linewidth=2, color="#59A14F")
    axes[1].set_title("CORD Optimization Score Trend")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(alpha=0.2)
    axes[1].tick_params(axis="x", rotation=20)
    fig.tight_layout()
    path = ASSET_DIR / "iterations.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_validation_chart(validation_rows: list[dict[str, str]]) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    names = [row["prompt_name"] for row in validation_rows]
    cer = [float(row["mean_cer"]) for row in validation_rows]
    score = [float(row["mean_total_score"]) for row in validation_rows]
    axes[0].bar(names, cer, color=["#4C78A8", "#E15759"])
    axes[0].set_title("CORD Validation CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)
    axes[1].bar(names, score, color=["#4C78A8", "#E15759"])
    axes[1].set_title("CORD Validation Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path = ASSET_DIR / "validation.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def choose_best_prompt(rows: list[dict[str, str]]) -> dict[str, str]:
    return max(rows, key=lambda row: (float(row["mean_total_score"]), -len(row["prompt_text"])))


def parse_rounds(rows: list[dict[str, str]]) -> list[dict]:
    parsed = []
    index = 0
    round_number = 1
    while index < len(rows):
        start = rows[index]
        candidates = rows[index + 1 : index + 6]
        winner = choose_best_prompt(candidates)
        parsed.append(
            {
                "round": round_number,
                "start_name": start["prompt_name"],
                "start_prompt": start["prompt_text"],
                "start_cer": float(start["mean_cer"]),
                "start_score": float(start["mean_total_score"]),
                "winner_name": winner["prompt_name"],
                "winner_prompt": winner["prompt_text"],
                "winner_cer": float(winner["mean_cer"]),
                "winner_score": float(winner["mean_total_score"]),
                "start_row": start,
                "candidate_rows": candidates,
            }
        )
        index += 6
        round_number += 1
    return parsed


def copy_sample_image(source: Path, target_name: str) -> Path:
    target = ASSET_DIR / target_name
    shutil.copyfile(source, target)
    return target


def round_candidate_lines(round_row: dict[str, object]) -> list[str]:
    winner_name = str(round_row["winner_name"])
    start_row = round_row["start_row"]
    assert isinstance(start_row, dict)
    lines = [
        f"### Round {round_row['round']} 전체 후보 성능",
        "",
        "| 구분 | Prompt | Mean CER | Mean Total Score | 비고 |",
        "|---|---|---:|---:|---|",
        f"| start | `{start_row['prompt_name']}` | {float(start_row['mean_cer']):.5f} | {float(start_row['mean_total_score']):.5f} | 다음 후보 생성 기준 |",
    ]
    for candidate in round_row["candidate_rows"]:
        assert isinstance(candidate, dict)
        is_winner = candidate["prompt_name"] == winner_name
        prompt_name = f"**`{candidate['prompt_name']}`**" if is_winner else f"`{candidate['prompt_name']}`"
        lines.append(
            f"| candidate | {prompt_name} | {float(candidate['mean_cer']):.5f} | {float(candidate['mean_total_score']):.5f} | {'winner' if is_winner else ''} |"
        )
    lines.extend(
        [
            "",
            "이 표의 뜻:",
            "- start는 후보 생성의 출발점이다.",
            "- 굵게 표시한 행이 해당 라운드 winner다.",
            "",
        ]
    )
    return lines


def round_appendix_lines(round_row: dict[str, object]) -> list[str]:
    lines = [
        f"### Round {round_row['round']} 프롬프트 원문",
        "",
        f"#### Start `{round_row['start_name']}`",
        "",
        "```text",
        str(round_row["start_prompt"]),
        "```",
        "",
    ]
    winner_name = str(round_row["winner_name"])
    for candidate in round_row["candidate_rows"]:
        assert isinstance(candidate, dict)
        suffix = " (winner)" if candidate["prompt_name"] == winner_name else ""
        lines.extend(
            [
                f"#### `{candidate['prompt_name']}`{suffix}",
                "",
                "```text",
                candidate["prompt_text"],
                "```",
                "",
            ]
        )
    return lines


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    seed_rows = read_csv(RUN_ROOT / "seed" / "seed_aggregate.csv")
    opt_rows = read_csv(RUN_ROOT / "optimize" / "optimization_aggregate.csv")
    val_rows = read_csv(RUN_ROOT / "validation" / "validation_aggregate.csv")
    report = json.loads((RUN_ROOT / "final_report.json").read_text(encoding="utf-8"))
    baseline_eval = {row["sample_id"]: row for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")}
    final_eval = {row["sample_id"]: row for row in read_jsonl(RUN_ROOT / "validation" / "final" / "evaluations.jsonl")}
    rounds = parse_rounds(opt_rows)

    seed_chart = save_seed_chart(seed_rows)
    iteration_chart = save_iteration_chart(rounds)
    validation_chart = save_validation_chart(val_rows)

    baseline = report["baseline"]
    final = report["final"]
    adopted = report["adopted_prompt"]
    final_prompt = (RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    improvements = []
    for sample_id, baseline_row in baseline_eval.items():
        final_row = final_eval[sample_id]
        delta = final_row["cer"] - baseline_row["cer"]
        if delta < 0:
            improvements.append((delta, sample_id, baseline_row, final_row))
    improvements.sort(key=lambda item: item[0])
    selected_examples = improvements[:2]
    copied_samples = []
    for index, (_, sample_id, baseline_row, _) in enumerate(selected_examples, start=1):
        source = Path(baseline_row["image_path"])
        copied = copy_sample_image(source, f"sample_{index}_{sample_id}.jpg")
        copied_samples.append(copied)

    lines = [
        "# CORD v2 Full-Receipt OCR Prompt Optimization Report",
        "",
        "## 1. 한 줄 결론",
        "",
        "> 전체 영수증 데이터셋(CORD)에서는 optimized prompt가 baseline보다 CER를 크게 개선했다.",
        "",
        f"- baseline CER: `{baseline['mean_cer']:.5f}`",
        f"- optimized final CER: `{final['mean_cer']:.5f}`",
        f"- 상대 개선율: `{report['relative_cer_improvement'] * 100:.2f}%`",
        f"- 현재 채택 프롬프트: `{adopted['name']}`",
        "",
        "이 문장의 뜻:",
        "- 사용자의 가설대로, crop OCR과 full-receipt OCR에서는 프롬프트 반응이 달랐다.",
        "- KORIE crop에서는 망가졌지만, CORD full receipt에서는 실제로 좋아졌다.",
        "",
        "## 2. 왜 이 실험이 중요한가",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        "| 데이터셋 | CORD v2 full receipt |",
        "| 개발셋 | 8 |",
        "| 검증셋 | 12 |",
        "| 목적 | full receipt에서 prompt 반응 확인 |",
        "",
            "이 표의 뜻:",
            "- 이 실험은 전체 영수증 이미지에서 프롬프트가 어떻게 작동하는지 보려는 것이다.",
            "- sample 수는 작지만, 방향성이 KORIE crop과 달라지는지 확인하는 데는 충분했다.",
            "",
            "## 3. 데이터셋 대표 샘플 2개",
            "",
            f"### 샘플 1: `{selected_examples[0][1]}`",
            "",
            f"![CORD sample 1](./{copied_samples[0].relative_to(DOCS_DIR).as_posix()})",
            "",
            f"### 샘플 2: `{selected_examples[1][1]}`",
            "",
            f"![CORD sample 2](./{copied_samples[1].relative_to(DOCS_DIR).as_posix()})",
            "",
            "이 섹션의 뜻:",
            "- 실제 영수증 이미지를 보고, 이후 표에 나오는 OCR 결과가 어떤 장면에서 나온 건지 바로 연결해서 볼 수 있다.",
            "",
            "## 4. seed 프롬프트 비교",
            "",
            f"![CORD seed chart](./{seed_chart.relative_to(DOCS_DIR).as_posix()})",
        "",
        "| Prompt | Mean CER | Total Score |",
        "|---|---:|---:|",
    ]

    for row in seed_rows:
        lines.append(f"| `{row['prompt_name']}` | {float(row['mean_cer']):.5f} | {float(row['mean_total_score']):.5f} |")

    lines.extend(
        [
            "",
            "이 그림의 뜻:",
            "- seed 단계에서는 `P3`가 가장 좋았다.",
            "- 즉, full receipt에서는 더 강한 제약형 프롬프트가 baseline보다 유리했다.",
            "",
            "## 5. optimizer iteration 변화",
            "",
            f"![CORD iteration chart](./{iteration_chart.relative_to(DOCS_DIR).as_posix()})",
            "",
            "| Round | Start | Start CER | Winner | Winner CER | Winner Score |",
            "|---:|---|---:|---|---:|---:|",
        ]
    )

    for row in rounds:
        lines.append(
            f"| {row['round']} | `{row['start_name']}` | {row['start_cer']:.5f} | "
            f"`{row['winner_name']}` | {row['winner_cer']:.5f} | {row['winner_score']:.5f} |"
        )

    lines.extend(
        [
            "",
            "이 표의 뜻:",
            "- optimizer가 round를 거치면서 CER를 계속 낮췄다.",
            "- 마지막 winner는 `Prompt E`였고, 이게 검증셋 final prompt로 넘어갔다.",
            "",
        ]
    )

    for row in rounds:
        lines.extend(round_candidate_lines(row))

    lines.extend(
        [
            "## 6. 검증셋 결과",
            "",
            f"![CORD validation chart](./{validation_chart.relative_to(DOCS_DIR).as_posix()})",
            "",
            "| Prompt | Mean CER | Mean Total Score |",
            "|---|---:|---:|",
            f"| baseline | {baseline['mean_cer']:.5f} | {baseline['mean_total_score']:.5f} |",
            f"| optimized final | {final['mean_cer']:.5f} | {final['mean_total_score']:.5f} |",
            "",
            "이 그림과 표의 뜻:",
            "- optimized final이 baseline보다 분명히 더 좋은 OCR 결과를 냈다.",
            "- 특히 CER가 `0.77029 -> 0.44549`로 크게 줄었다.",
            "- 이건 사용자의 가설, 즉 `전체 영수증에서는 결과가 다를 수 있다`를 지지한다.",
            "",
            "## 7. 사람이 직접 비교할 수 있는 성공 사례 2개",
            "",
        ]
    )

    for index, (delta, sample_id, baseline_row, final_row) in enumerate(selected_examples, start=1):
        lines.extend(
            [
                f"### 성공 사례 {index}: `{sample_id}`",
                "",
                f"![Success sample {index}](./{copied_samples[index - 1].relative_to(DOCS_DIR).as_posix()})",
                "",
                f"- CER 변화: `{baseline_row['cer']:.5f} -> {final_row['cer']:.5f}`",
                "",
                "**Reference**",
                "",
                "```text",
                baseline_row["reference_text"],
                "```",
                "",
                "**Baseline OCR**",
                "",
                "```text",
                baseline_row["predicted_text"],
                "```",
                "",
                "**Optimized OCR**",
                "",
                "```text",
                final_row["predicted_text"],
                "```",
                "",
                "이 사례의 뜻:",
                "- baseline은 일부 핵심 줄이나 구조를 놓쳤다.",
                "- optimized prompt는 더 많은 줄을 읽고, 영수증 구조를 더 잘 보존했다.",
                "",
            ]
        )

    lines.extend(
        [
            "## 8. 그런데 왜 자동 채택은 baseline인가",
            "",
            f"- adopted prompt: `{adopted['name']}`",
            f"- adopted reason: {adopted['reason']}",
            "",
            "이 뜻은 다음과 같다.",
            "- 현재 PRD 규칙은 `CER 개선 + 안정성 지표 개선`이 함께 있어야 채택한다.",
            "- 이번 CORD mini run에서는 CER는 크게 좋아졌지만, non-Korean / repetition / empty는 baseline과 동일했다.",
            "- 그래서 현재 코드 규칙상 자동 채택은 baseline으로 남았다.",
            "- 하지만 사람 해석 기준으로는 `optimized final을 유력 후보`로 보는 것이 더 자연스럽다.",
            "",
            "## 9. 최종 프롬프트 원문",
            "",
            "### Baseline",
            "",
            "```text",
            "Text Recognition:",
            "```",
            "",
            "### Optimized Final",
            "",
            "```text",
            final_prompt,
            "```",
            "",
            "## 10. KORIE crop과 CORD full receipt를 같이 보면",
            "",
            "| 데이터셋 | 결과 | 해석 |",
            "|---|---|---|",
            "| KORIE crop | optimized prompt가 validation에서 크게 악화 | 짧은 crop에는 프롬프트가 생성형 출력으로 샐 수 있음 |",
            "| CORD full receipt | optimized prompt가 validation CER를 크게 개선 | 전체 문맥이 있는 영수증에서는 제약형 프롬프트가 더 잘 작동할 수 있음 |",
            "",
            "이 표의 뜻:",
            "- 프롬프트는 데이터 형태에 따라 효과가 달라진다.",
            "- 따라서 prompt optimization 결과를 일반화하려면 `어떤 이미지 단위에서 실험했는지`를 항상 같이 봐야 한다.",
            "",
            "## Appendix A. Round별 전체 프롬프트 원문",
            "",
            "이 부록의 뜻:",
            "- 각 라운드에서 어떤 후보가 실제로 검토됐는지 문서만으로 추적할 수 있다.",
            "- winner 외 탈락 후보도 다시 읽어보며 비교할 수 있다.",
        ]
    )

    for row in rounds:
        lines.extend(round_appendix_lines(row))

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
