from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "runs" / "korean-ocr-img-text-pair-heldout-v3"
PREV_RUN_ROOT = ROOT / "runs" / "korean-ocr-img-text-pair-fast-english-opt"
DOCS_DIR = ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "007"
REPORT_PATH = DOCS_DIR / "007_heldout_benchmark_and_evaluation_upgrade_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def rel(path: Path) -> str:
    return path.relative_to(DOCS_DIR).as_posix()


def load_round_candidates() -> list[dict[str, object]]:
    optimization_rows = read_csv(RUN_ROOT / "optimize" / "optimization_aggregate.csv")
    rounds: list[dict[str, object]] = []
    idx = 0
    round_number = 1
    while idx < len(optimization_rows):
        start = optimization_rows[idx]
        candidates = optimization_rows[idx + 1 : idx + 6]
        winner = max(candidates, key=lambda row: float(row["mean_total_score"]))
        rounds.append(
            {
                "round": round_number,
                "start": start,
                "candidates": candidates,
                "winner_name": winner["prompt_name"],
            }
        )
        idx += 6
        round_number += 1
    return rounds


def save_seed_chart(seed_rows: list[dict[str, str]]) -> Path:
    labels = [row["prompt_name"] for row in seed_rows]
    cer = [float(row["mean_cer"]) for row in seed_rows]
    score = [float(row["mean_total_score"]) for row in seed_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(labels, cer, color=["#4C78A8", "#59A14F", "#F28E2B", "#E15759"])
    axes[0].set_title("Seed Prompt CER on Held-out Dev")
    axes[0].set_ylabel("Mean normalized CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, score, color=["#4C78A8", "#59A14F", "#F28E2B", "#E15759"])
    axes[1].set_title("Seed Prompt Total Score on Held-out Dev")
    axes[1].set_ylabel("Mean total score")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "seed.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_validation_chart(prev_validation: list[dict[str, str]], new_validation: list[dict[str, str]]) -> Path:
    labels = ["Prev baseline", "Prev optimized", "Held-out baseline", "Held-out optimized"]
    cer = [
        float(prev_validation[0]["mean_cer"]),
        float(prev_validation[1]["mean_cer"]),
        float(new_validation[0]["mean_cer"]),
        float(new_validation[1]["mean_cer"]),
    ]
    score = [
        float(prev_validation[0]["mean_total_score"]),
        float(prev_validation[1]["mean_total_score"]),
        float(new_validation[0]["mean_total_score"]),
        float(new_validation[1]["mean_total_score"]),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(labels, cer, color=["#9C755F", "#BAB0AC", "#4C78A8", "#E15759"])
    axes[0].set_title("Validation CER Comparison")
    axes[0].set_ylabel("Mean normalized CER")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, score, color=["#9C755F", "#BAB0AC", "#4C78A8", "#E15759"])
    axes[1].set_title("Validation Total Score Comparison")
    axes[1].set_ylabel("Mean total score")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_round_trend_chart(rounds: list[dict[str, object]]) -> Path:
    labels = ["Seed winner"] + [f"Round {row['round']}" for row in rounds]
    scores = [float(rounds[0]["start"]["mean_total_score"])] + [
        max(float(candidate["mean_total_score"]) for candidate in row["candidates"]) for row in rounds
    ]
    cer = [float(rounds[0]["start"]["mean_cer"])] + [
        min(float(candidate["mean_cer"]) for candidate in row["candidates"]) for row in rounds
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(labels, cer, marker="o", linewidth=2, color="#4C78A8")
    axes[0].set_title("Best CER by Optimization Round")
    axes[0].set_ylabel("Mean normalized CER")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].grid(alpha=0.2)

    axes[1].plot(labels, scores, marker="o", linewidth=2, color="#59A14F")
    axes[1].set_title("Best Total Score by Optimization Round")
    axes[1].set_ylabel("Mean total score")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].grid(alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "round_trends.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_metric_breakdown_chart(validation_rows: list[dict[str, str]]) -> Path:
    labels = [row["prompt_name"] for row in validation_rows]
    raw_cer = [float(row["mean_raw_cer"]) for row in validation_rows]
    cer = [float(row["mean_cer"]) for row in validation_rows]
    token_f1 = [float(row["mean_token_f1"]) for row in validation_rows]
    non_korean = [float(row["non_korean_rate"]) for row in validation_rows]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0, 0].bar(labels, raw_cer, color=["#4C78A8", "#E15759"])
    axes[0, 0].set_title("Mean Raw CER")
    axes[0, 0].grid(axis="y", alpha=0.2)

    axes[0, 1].bar(labels, cer, color=["#4C78A8", "#E15759"])
    axes[0, 1].set_title("Mean Normalized CER")
    axes[0, 1].grid(axis="y", alpha=0.2)

    axes[1, 0].bar(labels, token_f1, color=["#4C78A8", "#E15759"])
    axes[1, 0].set_title("Mean Token F1")
    axes[1, 0].grid(axis="y", alpha=0.2)

    axes[1, 1].bar(labels, non_korean, color=["#4C78A8", "#E15759"])
    axes[1, 1].set_title("Non-Korean Penalty Rate")
    axes[1, 1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "metric_breakdown.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_sample_delta_chart(samples: list[dict[str, object]]) -> Path:
    labels = [row["sample_id"] for row in samples]
    deltas = [row["delta"] for row in samples]
    colors = ["#59A14F" if delta < 0 else "#E15759" for delta in deltas]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("Sample-level CER Delta (Optimized - Baseline)")
    ax.set_xlabel("CER delta")
    ax.grid(axis="x", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "sample_delta.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def md_row(values: list[str]) -> str:
    return "| " + " | ".join(values) + " |"


def prompt_block(title: str, text: str) -> list[str]:
    return [title, "", "```text", text, "```", ""]


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    seed_rows = read_csv(RUN_ROOT / "seed" / "seed_aggregate.csv")
    prev_validation_rows = read_csv(PREV_RUN_ROOT / "validation" / "validation_aggregate.csv")
    validation_rows = read_csv(RUN_ROOT / "validation" / "validation_aggregate.csv")
    rounds = load_round_candidates()

    baseline_eval = {row["sample_id"]: row for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")}
    final_eval = read_jsonl(RUN_ROOT / "validation" / "final" / "evaluations.jsonl")
    samples = []
    for row in final_eval:
        base = baseline_eval[row["sample_id"]]
        samples.append(
            {
                **row,
                "baseline_text": base["predicted_text"],
                "baseline_cer": base["cer"],
                "delta": row["cer"] - base["cer"],
            }
        )
    samples.sort(key=lambda row: row["delta"])

    seed_chart = save_seed_chart(seed_rows)
    validation_chart = save_validation_chart(prev_validation_rows, validation_rows)
    round_chart = save_round_trend_chart(rounds)
    metric_chart = save_metric_breakdown_chart(validation_rows)
    sample_delta_chart = save_sample_delta_chart(samples)

    dataset_examples = [samples[0], samples[1]]
    best_case = samples[0]
    worst_case = samples[-1]
    non_korean_case = next((row for row in samples if row["penalties"]["non_korean_mixed"] > 0), worst_case)

    final_prompt = (RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    adopted_prompt = (RUN_ROOT / "adopted_prompt.txt").read_text(encoding="utf-8").strip()

    lines = [
        "# Held-out Benchmark And Evaluation Upgrade Report",
        "",
        "작성일: 2026-03-15",
        "",
        "## 1. 세 줄 요약",
        "",
        md_row(["질문", "답"]),
        md_row(["---", "---"]),
        md_row(["기존 fast subset보다 이번 실험이 더 믿을 만한가?", "예. `train` 기반 소형 subset 대신, 100개 전체에서 필터링 후 held-out split를 다시 만들었다."]),
        md_row(["optimizer가 결국 baseline을 이겼나?", "아니오. normalized CER는 좋아졌지만 non-Korean penalty가 생겨 채택은 baseline이다."]),
        md_row(["이번 보고서의 핵심 가치", "무엇이 바뀌었고, 왜 여전히 baseline이 채택됐는지 더 신뢰성 있게 보여준다."]),
        "",
        "이 표의 뜻:",
        "- 이번 보고서는 단순히 새 프롬프트를 자랑하는 문서가 아니다.",
        "- 실험이 얼마나 믿을 만한지부터 다시 점검한 뒤, 그 상태에서 다시 돌린 결과를 정리한 문서다.",
        "",
        "## 2. 왜 다시 실험했는가",
        "",
        md_row(["문제", "기존 상태"]),
        md_row(["---", "---"]),
        md_row(["테스트셋 신뢰도", "기존 fast subset은 공개 `train` split에서 다시 쪼갠 작은 내부 subset이었다."]),
        md_row(["평가 지표", "raw CER 위주였고 normalization이 약했다."]),
        md_row(["optimizer 구조", "실패 예시를 넣고 바로 후보 생성만 했다."]),
        md_row(["테스트 범위", "주로 단위 테스트였고, 평가/benchmark 신뢰성 검증이 약했다."]),
        "",
        "이 표의 뜻:",
        "- 기존 파이프라인은 돌아갔지만, 결론을 강하게 믿기엔 약한 부분이 있었다.",
        "- 그래서 이번에는 `실험 자체의 신뢰성`을 먼저 보강했다.",
        "",
        "## 3. 무엇을 바꿨는가",
        "",
        md_row(["영역", "개선 내용"]),
        md_row(["---", "---"]),
        md_row(["Benchmark", "100개 전체 manifest를 합친 뒤, 길이/비율 필터링 후 stratified held-out split `dev 16 / val 16` 생성"]),
        md_row(["Evaluation", "`raw CER + normalized CER + token F1`를 함께 기록하고, penalty를 reference-aware로 수정"]),
        md_row(["Optimizer", "`failure analysis -> candidate generation` 2단계 구조로 변경"]),
        md_row(["Tests", "dataset merge/filter/split, normalization, token F1, optimizer payload를 테스트에 추가"]),
        "",
        "이 표의 뜻:",
        "- 이번 개선은 프롬프트 문구 몇 줄 바꾼 것이 아니다.",
        "- benchmark, metric, optimizer를 한꺼번에 바꿔서 결과 해석이 더 단단해졌다.",
        "",
        "## 4. Seed Prompt 비교",
        "",
        f"![Seed chart](./{rel(seed_chart)})",
        "",
        md_row(["Prompt", "Mean normalized CER", "Mean token F1", "Mean total score"]),
        md_row(["---", "---:", "---:", "---:"]),
    ]

    for row in seed_rows:
        lines.append(
            md_row(
                [
                    f"`{row['prompt_name']}`",
                    f"{float(row['mean_cer']):.4f}",
                    f"{float(row['mean_token_f1']):.4f}",
                    f"{float(row['mean_total_score']):.4f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트와 표의 뜻:",
            "- held-out dev에서는 `P1`이 가장 강했다.",
            "- 즉, 시작점은 여전히 짧은 영어 exact-transcription 프롬프트가 가장 좋았다.",
            "",
            "### Seed prompt 원문",
            "",
        ]
    )

    for row in seed_rows:
        lines.extend(prompt_block(f"#### `{row['prompt_name']}`", row["prompt_text"]))

    lines.extend(
        [
            "## 5. Optimization 흐름",
            "",
            f"![Round trend chart](./{rel(round_chart)})",
            "",
            "이 차트의 뜻:",
            "- 각 라운드에서 최고 점수 후보가 어떻게 변했는지 보여준다.",
            "- 이번 실험에서는 seed winner를 크게 넘어서는 후보가 나오지 않았다.",
            "",
        ]
    )

    for round_info in rounds:
        lines.extend(
            [
                f"### Round {round_info['round']}",
                "",
                md_row(["Prompt", "Mean normalized CER", "Mean token F1", "Mean total score", "Winner"]),
                md_row(["---", "---:", "---:", "---:", "---"]),
                md_row(
                    [
                        f"`{round_info['start']['prompt_name']}` start",
                        f"{float(round_info['start']['mean_cer']):.4f}",
                        f"{float(round_info['start']['mean_token_f1']):.4f}",
                        f"{float(round_info['start']['mean_total_score']):.4f}",
                        "",
                    ]
                ),
            ]
        )
        for candidate in round_info["candidates"]:
            winner_mark = "**WINNER**" if candidate["prompt_name"] == round_info["winner_name"] else ""
            lines.append(
                md_row(
                    [
                        f"`{candidate['prompt_name']}`",
                        f"{float(candidate['mean_cer']):.4f}",
                        f"{float(candidate['mean_token_f1']):.4f}",
                        f"{float(candidate['mean_total_score']):.4f}",
                        winner_mark,
                    ]
                )
            )
        lines.extend(["", "Round 프롬프트 원문:", ""])
        lines.extend(prompt_block("Start prompt", round_info["start"]["prompt_text"]))
        for candidate in round_info["candidates"]:
            title = f"Candidate `{candidate['prompt_name']}`"
            if candidate["prompt_name"] == round_info["winner_name"]:
                title += " **WINNER**"
            lines.extend(prompt_block(title, candidate["prompt_text"]))

    lines.extend(
        [
            "## 6. Validation 비교",
            "",
            f"![Validation comparison](./{rel(validation_chart)})",
            "",
            md_row(["Setting", "Mean normalized CER", "Mean total score"]),
            md_row(["---", "---:", "---:"]),
            md_row(["`prev fast baseline`", f"{float(prev_validation_rows[0]['mean_cer']):.4f}", f"{float(prev_validation_rows[0]['mean_total_score']):.4f}"]),
            md_row(["`prev fast optimized`", f"{float(prev_validation_rows[1]['mean_cer']):.4f}", f"{float(prev_validation_rows[1]['mean_total_score']):.4f}"]),
            md_row(["`held-out baseline`", f"{float(validation_rows[0]['mean_cer']):.4f}", f"{float(validation_rows[0]['mean_total_score']):.4f}"]),
            md_row(["`held-out optimized`", f"{float(validation_rows[1]['mean_cer']):.4f}", f"{float(validation_rows[1]['mean_total_score']):.4f}"]),
            "",
            "이 차트와 표의 뜻:",
            "- held-out benchmark에서는 optimized가 normalized CER 기준으로 baseline보다 조금 좋았다.",
            "- 하지만 안정성 규칙을 같이 보면 non-Korean penalty가 새로 생겨서 최종 채택은 실패했다.",
            "",
            f"![Metric breakdown](./{rel(metric_chart)})",
            "",
            "이 차트의 뜻:",
            "- raw CER와 normalized CER는 optimized 쪽이 조금 더 좋다.",
            "- 하지만 token F1은 baseline이 더 높고, non-Korean penalty가 optimized에서만 발생했다.",
            "- 즉, 문자 단위 편집 거리는 좋아졌지만 사람이 보기엔 더 이상한 문자가 섞인 사례가 있었다.",
            "",
            "### 최종 프롬프트",
            "",
        ]
    )

    lines.extend(prompt_block("Optimized prompt", final_prompt))
    lines.extend(prompt_block("Adopted prompt", adopted_prompt))

    lines.extend(
        [
            "## 7. 샘플별 변화",
            "",
            f"![Sample delta chart](./{rel(sample_delta_chart)})",
            "",
            md_row(["Sample", "Baseline CER", "Optimized CER", "Delta", "Non-Korean penalty"]),
            md_row(["---", "---:", "---:", "---:", "---:"]),
        ]
    )

    for row in samples:
        lines.append(
            md_row(
                [
                    f"`{row['sample_id']}`",
                    f"{row['baseline_cer']:.4f}",
                    f"{row['cer']:.4f}",
                    f"{row['delta']:+.4f}",
                    f"{row['penalties']['non_korean_mixed']:.2f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트의 뜻:",
            "- 일부 샘플에서는 optimized가 실제로 좋아졌다.",
            "- 하지만 `[unclear]`류 규칙이 들어간 뒤 CJK/비한국어 문자가 섞인 사례가 생기면서 안정성 규칙을 통과하지 못했다.",
            "",
            "## 8. 데이터셋 대표 샘플 2개",
            "",
        ]
    )

    for idx, row in enumerate(dataset_examples, start=1):
        image_path = ROOT / str(row["image_path"])
        lines.extend(
            [
                f"### 대표 샘플 {idx}: `{row['sample_id']}`",
                "",
                f"![{row['sample_id']}]({Path('..') / image_path.relative_to(ROOT)})",
                "",
                "```text",
                str(row["reference_text"]),
                "```",
                "",
                "이 샘플의 뜻:",
                "- 이 데이터셋은 영수증 전체가 아니라 한국어 OCR line 이미지다.",
                "- 그래서 읽기 순서보다는 `글자 전사 정확도`가 더 직접적으로 드러난다.",
                "",
            ]
        )

    def sample_section(title: str, row: dict[str, object], note: str) -> list[str]:
        image_path = ROOT / str(row["image_path"])
        return [
            f"### {title}: `{row['sample_id']}`",
            "",
            f"![{row['sample_id']}]({Path('..') / image_path.relative_to(ROOT)})",
            "",
            "**Reference**",
            "",
            "```text",
            str(row["reference_text"]),
            "```",
            "",
            "**Baseline OCR**",
            "",
            "```text",
            str(row["baseline_text"]),
            "```",
            "",
            "**Optimized OCR**",
            "",
            "```text",
            str(row["predicted_text"]),
            "```",
            "",
            note,
            "",
        ]

    lines.extend(["## 9. 실제 비교 사례", ""])
    lines.extend(
        sample_section(
            "Optimized가 더 나은 사례",
            best_case,
            f"이 사례의 뜻: baseline 대비 CER 변화는 `{best_case['delta']:+.4f}`다.",
        )
    )
    lines.extend(
        sample_section(
            "Optimized가 더 나쁜 사례",
            worst_case,
            f"이 사례의 뜻: baseline 대비 CER 변화는 `{worst_case['delta']:+.4f}`다.",
        )
    )
    lines.extend(
        sample_section(
            "채택 실패를 만든 사례",
            non_korean_case,
            "이 사례의 뜻: optimized가 일부 문자를 더 가깝게 맞췄더라도, 비한국어 문자가 섞이면 PRD 채택 규칙에서는 탈락할 수 있다.",
        )
    )

    lines.extend(
        [
            "## 10. 해석",
            "",
            "이번 실험에서 확인된 것은 네 가지다.",
            "",
            "1. 기존 fast subset보다 held-out benchmark가 더 신뢰할 만하다.",
            "2. optimizer는 normalized CER를 약간 개선할 수 있었다.",
            "3. 하지만 안정성 규칙을 같이 보면 baseline을 대체할 정도는 아니다.",
            "4. 특히 `[unclear]` 같은 placeholder 전략은 이 프로젝트의 채택 규칙과 잘 맞지 않는다.",
            "",
            "다음 단계는 이게 맞다.",
            "",
            "1. optimizer에서 `[unclear]`나 비원문 placeholder를 금지한다.",
            "2. non-Korean penalty가 생긴 사례를 따로 분류해서 rewrite instruction에 직접 반영한다.",
            "3. line OCR benchmark와 receipt OCR benchmark를 분리해서 보고서를 따로 유지한다.",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
