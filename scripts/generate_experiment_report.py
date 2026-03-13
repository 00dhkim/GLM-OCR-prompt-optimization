from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "runs" / "korie-ocr-full"
DOCS_DIR = ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "001"
REPORT_PATH = DOCS_DIR / "001_glm_ocr_prompt_optimization_report.md"


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
    names = [row["prompt_name"] for row in seed_rows]
    cer = [float(row["mean_cer"]) for row in seed_rows]
    score = [float(row["mean_total_score"]) for row in seed_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(names, cer, color=["#4C78A8", "#59A14F", "#F28E2B", "#E15759"])
    axes[0].set_title("Seed Prompt CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(names, score, color=["#4C78A8", "#59A14F", "#F28E2B", "#E15759"])
    axes[1].set_title("Seed Prompt Total Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "seed_prompt_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_iteration_chart(round_rows: list[dict[str, str]]) -> Path:
    labels = [row["label"] for row in round_rows]
    cer = [row["mean_cer"] for row in round_rows]
    score = [row["mean_total_score"] for row in round_rows]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    axes[0].plot(labels, cer, marker="o", linewidth=2, color="#4C78A8")
    axes[0].set_title("Optimization Trend on Dev Set")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(alpha=0.2)
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].plot(labels, score, marker="o", linewidth=2, color="#59A14F")
    axes[1].set_title("Optimization Score Trend on Dev Set")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(alpha=0.2)
    axes[1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    path = ASSET_DIR / "optimization_iterations.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_validation_chart(validation_rows: list[dict[str, str]]) -> Path:
    names = [row["prompt_name"] for row in validation_rows]
    cer = [float(row["mean_cer"]) for row in validation_rows]
    score = [float(row["mean_total_score"]) for row in validation_rows]
    empty_rate = [float(row["empty_rate"]) for row in validation_rows]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].bar(names, cer, color=["#4C78A8", "#E15759"])
    axes[0].set_title("Validation CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(names, score, color=["#4C78A8", "#E15759"])
    axes[1].set_title("Validation Total Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)

    axes[2].bar(names, empty_rate, color=["#4C78A8", "#E15759"])
    axes[2].set_title("Validation Empty Rate")
    axes[2].set_ylabel("Empty Rate")
    axes[2].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_category_chart(category_rows: list[dict]) -> Path:
    labels = [row["category"] for row in category_rows]
    deltas = [row["delta"] for row in category_rows]
    colors = ["#E15759" if delta > 0 else "#59A14F" for delta in deltas]

    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("Category-Level CER Change (Optimized - Baseline)")
    ax.set_xlabel("CER Delta")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    path = ASSET_DIR / "category_delta.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def parse_rounds(rows: list[dict[str, str]]) -> list[dict[str, object]]:
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
                "start_prompt": start["prompt_text"],
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


def prompt_section(title: str, name: str, prompt_text: str) -> str:
    return f"### {title}: `{name}`\n\n```text\n{prompt_text}\n```\n"


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    seed_rows = read_csv(RUN_ROOT / "seed" / "seed_aggregate.csv")
    optimization_rows = read_csv(RUN_ROOT / "optimize" / "optimization_aggregate.csv")
    validation_rows = read_csv(RUN_ROOT / "validation" / "validation_aggregate.csv")
    baseline_eval = {row["sample_id"]: row for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")}
    final_eval = {row["sample_id"]: row for row in read_jsonl(RUN_ROOT / "validation" / "final" / "evaluations.jsonl")}

    round_rows = parse_rounds(optimization_rows)
    iteration_plot_rows = [
        {"label": "Seed winner", "mean_cer": float(seed_rows[1]["mean_cer"]), "mean_total_score": float(seed_rows[1]["mean_total_score"])},
        {"label": "Round 1 winner", "mean_cer": round_rows[0]["winner_cer"], "mean_total_score": round_rows[0]["winner_score"]},
        {"label": "Round 2 winner", "mean_cer": round_rows[1]["winner_cer"], "mean_total_score": round_rows[1]["winner_score"]},
        {"label": "Round 3 winner", "mean_cer": round_rows[2]["winner_cer"], "mean_total_score": round_rows[2]["winner_score"]},
    ]

    category_agg: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "base": 0.0, "final": 0.0})
    deltas = []
    for sample_id, baseline_row in baseline_eval.items():
        final_row = final_eval[sample_id]
        category = "_".join(sample_id.split("_")[1:]) if "_" in sample_id else "unknown"
        category_agg[category]["n"] += 1
        category_agg[category]["base"] += baseline_row["cer"]
        category_agg[category]["final"] += final_row["cer"]
        deltas.append(
            {
                "sample_id": sample_id,
                "category": category,
                "baseline_cer": baseline_row["cer"],
                "final_cer": final_row["cer"],
                "delta": final_row["cer"] - baseline_row["cer"],
                "reference_text": baseline_row["reference_text"],
                "baseline_text": baseline_row["predicted_text"],
                "final_text": final_row["predicted_text"],
            }
        )

    category_rows = []
    for category, values in category_agg.items():
        baseline_mean = values["base"] / values["n"]
        final_mean = values["final"] / values["n"]
        category_rows.append(
            {
                "category": category,
                "n": int(values["n"]),
                "baseline_mean": baseline_mean,
                "final_mean": final_mean,
                "delta": final_mean - baseline_mean,
            }
        )
    category_rows.sort(key=lambda row: row["delta"])
    top_category_rows = category_rows[:5] + category_rows[-5:]

    deltas.sort(key=lambda row: row["delta"])
    best_examples = deltas[:5]
    worst_examples = deltas[-5:]

    seed_chart = save_seed_chart(seed_rows)
    iteration_chart = save_iteration_chart(iteration_plot_rows)
    validation_chart = save_validation_chart(validation_rows)
    category_chart = save_category_chart(top_category_rows)

    baseline_prompt = "Text Recognition:"
    optimized_prompt = (RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    adopted_prompt = (RUN_ROOT / "adopted_prompt.txt").read_text(encoding="utf-8").strip()

    seed_best = min(seed_rows, key=lambda row: float(row["mean_cer"]))

    lines = [
        "# GLM-OCR Prompt Optimization Report",
        "",
        "## 1. 한눈에 보는 결론",
        "",
        "이 실험의 핵심 질문은 이것이다.",
        "",
        "> `기본 프롬프트보다 더 좋은 프롬프트를 찾았는가?`",
        "",
        "답은 `아니오`다.",
        "",
        "| 질문 | 답 |",
        "|---|---|",
        "| optimizer가 새 프롬프트를 만들었나? | 예 |",
        "| 개발셋에서는 조금 좋아졌나? | 예 |",
        "| 검증셋에서도 좋아졌나? | 아니오 |",
        "| 최종 채택 프롬프트는? | baseline `Text Recognition:` |",
        "",
        "이 표의 뜻:",
        "- 개발셋에서는 optimizer가 그럴듯한 개선을 찾았다.",
        "- 하지만 진짜 중요한 검증셋에서는 성능이 크게 나빠졌다.",
        "- 그래서 PRD 규칙대로 baseline을 유지했다.",
        "",
        "## 2. 이번 실험이 무엇을 한 것인가",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        "| 데이터 | KORIE 공개 OCR crop split |",
        "| 개발셋 | 60개 |",
        "| 검증셋 | 100개 |",
        "| OCR 모델 | Ollama GLM-OCR |",
        "| optimizer | gpt-5-nano |",
        "| 주지표 | CER |",
        "",
        "이 표의 뜻:",
        "- 이번 데이터는 `전체 영수증 사진`이 아니라 `잘라낸 OCR 조각 이미지`다.",
        "- 그래서 이번 결과는 full-receipt OCR보다는 crop OCR 성향을 더 많이 반영한다.",
        "",
        "## 3. seed 프롬프트 4개 비교",
        "",
        f"![Seed prompt chart](./{seed_chart.relative_to(DOCS_DIR).as_posix()})",
        "",
        "| Prompt | Mean CER | Total Score | Non-Korean Rate | Empty Rate |",
        "|---|---:|---:|---:|---:|",
    ]

    for row in seed_rows:
        lines.append(
            f"| `{row['prompt_name']}` | {float(row['mean_cer']):.5f} | {float(row['mean_total_score']):.5f} | "
            f"{float(row['non_korean_rate'])*100:.2f}% | {float(row['empty_rate'])*100:.2f}% |"
        )

    lines.extend(
        [
            "",
            "이 그림과 표의 뜻:",
            "- 왼쪽 막대는 `글자를 얼마나 틀렸는지`를 보여준다. CER는 낮을수록 좋다.",
            "- 오른쪽 막대는 CER와 패널티를 합친 점수다. 높을수록 좋다.",
            f"- 여기서 가장 무난했던 시작점은 `{seed_best['prompt_name']}`였다.",
            "",
            "### seed 프롬프트 원문",
            "",
        ]
    )

    for row in seed_rows:
        lines.append(prompt_section("Prompt", row["prompt_name"], row["prompt_text"]))

    lines.extend(
        [
            "## 4. iteration별 변화",
            "",
            f"![Iteration chart](./{iteration_chart.relative_to(DOCS_DIR).as_posix()})",
            "",
            "| Round | 시작 프롬프트 | 시작 CER | 시작 Score | 승자 프롬프트 | 승자 CER | 승자 Score |",
            "|---:|---|---:|---:|---|---:|---:|",
        ]
    )

    for row in round_rows:
        lines.append(
            f"| {row['round']} | `{row['start_name']}` | {row['start_cer']:.6f} | {row['start_score']:.6f} | "
            f"`{row['winner_name']}` | {row['winner_cer']:.6f} | {row['winner_score']:.6f} |"
        )

    lines.extend(
        [
            "",
            "이 그림과 표의 뜻:",
            "- optimizer는 매 라운드마다 새 후보 5개를 만들고, 그중 점수가 가장 좋은 것을 다음 라운드로 넘겼다.",
            "- 개발셋에서는 CER가 아주 조금씩 내려갔다.",
            "- 하지만 좋아진 폭이 너무 작아서, 나중에 검증셋에서 무너질 위험이 있었다.",
            "",
            "### iteration에서 선택된 프롬프트 원문",
            "",
        ]
    )

    for row in round_rows:
        lines.append(prompt_section(f"Round {row['round']} start", row["start_name"], row["start_prompt"]))
        lines.append(prompt_section(f"Round {row['round']} winner", row["winner_name"], row["winner_prompt"]))

    baseline_row = next(row for row in validation_rows if row["prompt_name"] == "baseline")
    final_row = next(row for row in validation_rows if row["prompt_name"] == "final")

    lines.extend(
        [
            "## 5. 검증셋에서 정말 좋아졌는가",
            "",
            f"![Validation chart](./{validation_chart.relative_to(DOCS_DIR).as_posix()})",
            "",
            "| Prompt | Mean CER | Total Score | Non-Korean Rate | Empty Rate |",
            "|---|---:|---:|---:|---:|",
            f"| Baseline | {float(baseline_row['mean_cer']):.5f} | {float(baseline_row['mean_total_score']):.5f} | {float(baseline_row['non_korean_rate'])*100:.2f}% | {float(baseline_row['empty_rate'])*100:.2f}% |",
            f"| Optimized final | {float(final_row['mean_cer']):.5f} | {float(final_row['mean_total_score']):.5f} | {float(final_row['non_korean_rate'])*100:.2f}% | {float(final_row['empty_rate'])*100:.2f}% |",
            "",
            "이 그림과 표의 뜻:",
            "- 첫 번째 그래프는 CER 비교다. optimized final이 baseline보다 훨씬 높다. 즉, 훨씬 더 많이 틀렸다.",
            "- 두 번째 그래프는 종합 점수다. optimized final은 아예 음수까지 내려갔다.",
            "- 세 번째 그래프는 empty rate다. optimized final이 오히려 더 자주 비거나 이상한 출력을 냈다.",
            "",
            "### 최종 프롬프트 원문",
            "",
            prompt_section("Baseline", "baseline", baseline_prompt),
            prompt_section("Optimized final", "final", optimized_prompt),
            prompt_section("Adopted", "adopted", adopted_prompt),
            "## 6. 왜 baseline이 최종 채택됐는가",
            "",
            "| PRD 규칙 | 실제 결과 | 판정 |",
            "|---|---|---|",
            f"| validation CER가 더 좋아야 함 | {float(baseline_row['mean_cer']):.5f} -> {float(final_row['mean_cer']):.5f} | 실패 |",
            f"| 안정성도 좋아져야 함 | non-Korean은 좋아졌지만 empty는 {float(baseline_row['empty_rate'])*100:.2f}% -> {float(final_row['empty_rate'])*100:.2f}% | 실패 |",
            "| 너무 길고 불안정하면 탈락 | 실제로 일부 샘플에서 markdown / LaTeX / prompt echo 발생 | 실패 |",
            "",
            "이 표의 뜻:",
            "- optimized final은 일부 샘플에서 잘 맞았지만, 전체적으로는 더 나쁜 프롬프트였다.",
            "- 그래서 '새 프롬프트를 찾았다'가 아니라 'baseline을 유지해야 한다'가 이번 실험의 진짜 결론이다.",
            "",
            "## 7. 어떤 샘플은 왜 좋아졌고, 어떤 샘플은 왜 망가졌는가",
            "",
            "### 좋아진 사례 5개",
            "",
            "| Sample | Category | Baseline CER | Final CER | 변화 |",
            "|---|---|---:|---:|---:|",
        ]
    )

    for row in best_examples:
        lines.append(
            f"| `{row['sample_id']}` | `{row['category']}` | {row['baseline_cer']:.4f} | {row['final_cer']:.4f} | {row['delta']:+.4f} |"
        )

    lines.extend(
        [
            "",
            "### 망가진 사례 5개",
            "",
            "| Sample | Category | Baseline CER | Final CER | 변화 |",
            "|---|---|---:|---:|---:|",
        ]
    )

    for row in worst_examples:
        lines.append(
            f"| `{row['sample_id']}` | `{row['category']}` | {row['baseline_cer']:.4f} | {row['final_cer']:.4f} | {row['delta']:+.4f} |"
        )

    lines.extend(
        [
            "",
            "이 표의 뜻:",
            "- optimized prompt는 `전화번호`, `시간`처럼 짧고 구조가 뚜렷한 항목에서는 가끔 도움이 됐다.",
            "- 반대로 `수량`, `날짜`, `상호명`처럼 모호하거나 짧은 crop에서는 오히려 설명문이나 형식 텍스트를 뱉는 경우가 생겼다.",
            "",
            "### 가장 심한 실패 패턴",
            "",
            "| 패턴 | 뜻 | 실제 예시 |",
            "|---|---|---|",
            "| Prompt echo | 모델이 이미지 글자가 아니라 프롬프트 문장 자체를 출력 | `IMG00664_Item_Quantity_Item_Weight` |",
            "| Markdown fence | OCR 대신 ```markdown 같은 형식을 출력 | `IMG00670_MerchantName` |",
            "| LaTeX formatting | 텍스트를 수식처럼 꾸며서 출력 | `IMG00475_PaymentDate` |",
            "| Line reordering | 줄 순서가 바뀜 | `IMG00494_ReceiptNumber` |",
            "",
            "## 8. 카테고리별로 보면 어디서 특히 나빠졌는가",
            "",
            f"![Category delta chart](./{category_chart.relative_to(DOCS_DIR).as_posix()})",
            "",
            "| Category | N | Baseline CER | Final CER | Delta |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for row in top_category_rows:
        lines.append(
            f"| `{row['category']}` | {row['n']} | {row['baseline_mean']:.4f} | {row['final_mean']:.4f} | {row['delta']:+.4f} |"
        )

    lines.extend(
        [
            "",
            "이 그림과 표의 뜻:",
            "- 초록색은 optimized prompt가 더 좋아진 카테고리다.",
            "- 빨간색은 optimized prompt가 더 나빠진 카테고리다.",
            "- 특히 `Item_Quantity_Item_Weight`, `PaymentDate`, `MerchantName`에서 악화가 컸다.",
            "",
            "## 9. 고등학생 버전으로 아주 쉽게 정리하면",
            "",
            "1. 기본 프롬프트에서 시작했다.",
            "2. optimizer가 '이렇게 말하면 더 잘 읽을지도 몰라' 하는 새 프롬프트를 여러 개 만들었다.",
            "3. 개발셋에서는 새 프롬프트가 아주 조금 더 좋아 보였다.",
            "4. 그런데 새로운 문제집인 검증셋에 넣어 보니 오히려 성적이 크게 떨어졌다.",
            "5. 그래서 최종 답은 '새 프롬프트 채택'이 아니라 '기본 프롬프트 유지'다.",
            "",
            "## 10. 다음 실험에서 바로 바꿔야 할 점",
            "",
            "| 제안 | 이유 |",
            "|---|---|",
            "| 프롬프트를 더 짧게 제한 | 긴 지시문이 OCR 대신 생성형 출력을 유도할 수 있음 |",
            "| markdown / LaTeX / meta-text 금지를 명시 | 실제 회귀 사례가 이 패턴으로 나타남 |",
            "| category별로 따로 최적화 | 전화번호/시간과 수량/날짜는 반응이 다름 |",
            "| full-receipt 데이터로 다시 검증 | 현재 공개 데이터는 crop OCR이라 PRD 원래 목표와 다름 |",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
