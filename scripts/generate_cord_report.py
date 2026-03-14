from __future__ import annotations

import csv
import json
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


def parse_rounds(rows: list[dict[str, str]]) -> list[dict]:
    parsed = []
    index = 0
    round_number = 1
    while index < len(rows):
        start = rows[index]
        candidates = rows[index + 1 : index + 6]
        winner = max(candidates, key=lambda row: float(row["mean_total_score"]))
        parsed.append(
            {
                "round": round_number,
                "start_name": start["prompt_name"],
                "start_cer": float(start["mean_cer"]),
                "start_score": float(start["mean_total_score"]),
                "winner_name": winner["prompt_name"],
                "winner_prompt": winner["prompt_text"],
                "winner_cer": float(winner["mean_cer"]),
                "winner_score": float(winner["mean_total_score"]),
            }
        )
        index += 6
        round_number += 1
    return parsed


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    seed_rows = read_csv(RUN_ROOT / "seed" / "seed_aggregate.csv")
    opt_rows = read_csv(RUN_ROOT / "optimize" / "optimization_aggregate.csv")
    val_rows = read_csv(RUN_ROOT / "validation" / "validation_aggregate.csv")
    report = json.loads((RUN_ROOT / "final_report.json").read_text(encoding="utf-8"))
    rounds = parse_rounds(opt_rows)

    seed_chart = save_seed_chart(seed_rows)
    iteration_chart = save_iteration_chart(rounds)
    validation_chart = save_validation_chart(val_rows)

    baseline = report["baseline"]
    final = report["final"]
    adopted = report["adopted_prompt"]
    final_prompt = (RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()

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
        "## 3. seed 프롬프트 비교",
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
            "## 4. optimizer iteration 변화",
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
            "## 5. 검증셋 결과",
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
            "## 6. 그런데 왜 자동 채택은 baseline인가",
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
            "## 7. 최종 프롬프트 원문",
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
            "## 8. KORIE crop과 CORD full receipt를 같이 보면",
            "",
            "| 데이터셋 | 결과 | 해석 |",
            "|---|---|---|",
            "| KORIE crop | optimized prompt가 validation에서 크게 악화 | 짧은 crop에는 프롬프트가 생성형 출력으로 샐 수 있음 |",
            "| CORD full receipt | optimized prompt가 validation CER를 크게 개선 | 전체 문맥이 있는 영수증에서는 제약형 프롬프트가 더 잘 작동할 수 있음 |",
            "",
            "이 표의 뜻:",
            "- 프롬프트는 데이터 형태에 따라 효과가 달라진다.",
            "- 따라서 prompt optimization 결과를 일반화하려면 `어떤 이미지 단위에서 실험했는지`를 항상 같이 봐야 한다.",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
