from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "runs" / "korean-ocr-img-text-pair-fast-english-opt"
PREV_RUN_ROOT = ROOT / "runs" / "korean-ocr-img-text-pair-fast"
DOCS_DIR = ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "006"
REPORT_PATH = DOCS_DIR / "006_english_first_optimizer_report.md"


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


def rel(path: Path) -> str:
    return path.relative_to(DOCS_DIR).as_posix()


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
    path = ASSET_DIR / "seed.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_round_chart(round_rows: list[dict[str, object]]) -> Path:
    labels = ["Seed winner"] + [f"Round {row['round']} winner" for row in round_rows]
    cer = [round_rows[0]["start_cer"]] + [row["winner_cer"] for row in round_rows]
    score = [round_rows[0]["start_score"]] + [row["winner_score"] for row in round_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(labels, cer, marker="o", linewidth=2, color="#4C78A8")
    axes[0].set_title("Dev CER by Round")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(alpha=0.2)
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].plot(labels, score, marker="o", linewidth=2, color="#59A14F")
    axes[1].set_title("Dev Total Score by Round")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(alpha=0.2)
    axes[1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    path = ASSET_DIR / "rounds.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_validation_chart(prev_validation: list[dict[str, str]], new_validation: list[dict[str, str]]) -> Path:
    baseline = float(new_validation[0]["mean_cer"])
    prev_final = float(prev_validation[1]["mean_cer"])
    new_final = float(new_validation[1]["mean_cer"])

    score_baseline = float(new_validation[0]["mean_total_score"])
    score_prev = float(prev_validation[1]["mean_total_score"])
    score_new = float(new_validation[1]["mean_total_score"])

    labels = ["Baseline", "Old optimized", "New optimized"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].bar(labels, [baseline, prev_final, new_final], color=["#4C78A8", "#E15759", "#76B7B2"])
    axes[0].set_title("Validation CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, [score_baseline, score_prev, score_new], color=["#4C78A8", "#E15759", "#76B7B2"])
    axes[1].set_title("Validation Total Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_sample_delta_chart(sample_rows: list[dict[str, object]]) -> Path:
    labels = [row["sample_id"] for row in sample_rows]
    deltas = [row["delta"] for row in sample_rows]
    colors = ["#59A14F" if delta < 0 else "#E15759" for delta in deltas]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("Validation CER Delta per Sample (New optimized - Baseline)")
    ax.set_xlabel("CER delta")
    ax.grid(axis="x", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "sample_delta.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_prompt_length_chart(seed_rows: list[dict[str, str]], optimization_rows: list[dict[str, str]]) -> Path:
    rows = seed_rows + optimization_rows
    lengths = [len(row["prompt_text"]) for row in rows]
    scores = [float(row["mean_total_score"]) for row in rows]
    labels = [row["prompt_name"] for row in rows]

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.scatter(lengths, scores, color="#4C78A8", alpha=0.8)
    for x, y, label in zip(lengths, scores, labels, strict=False):
        ax.annotate(label, (x, y), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_title("Prompt Length vs Dev Total Score")
    ax.set_xlabel("Prompt length (characters)")
    ax.set_ylabel("Mean total score")
    ax.grid(alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "prompt_length_vs_score.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def choose_best_prompt(rows: list[dict[str, str]]) -> dict[str, str]:
    return max(rows, key=lambda row: (float(row["mean_total_score"]), -len(row["prompt_text"])))


def parse_rounds(optimization_rows: list[dict[str, str]], candidates_per_round: int = 5) -> list[dict[str, object]]:
    parsed = []
    index = 0
    round_number = 1
    while index < len(optimization_rows):
        start = optimization_rows[index]
        candidates = optimization_rows[index + 1 : index + 1 + candidates_per_round]
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
        index += 1 + candidates_per_round
        round_number += 1
    return parsed


def md_table_row(values: list[str]) -> str:
    return "| " + " | ".join(values) + " |"


def format_prompt_name(name: str, *, is_winner: bool) -> str:
    label = f"`{name}`"
    return f"**{label}**" if is_winner else label


def round_candidate_table(round_row: dict[str, object]) -> list[str]:
    winner_name = str(round_row["winner_name"])
    start_row = round_row["start_row"]
    assert isinstance(start_row, dict)
    lines = [
        f"### Round {round_row['round']} 전체 후보 성능",
        "",
        md_table_row(["구분", "Prompt", "Mean CER", "Mean Total Score", "비고"]),
        md_table_row(["---", "---", "---:", "---:", "---"]),
        md_table_row(
            [
                "start",
                format_prompt_name(start_row["prompt_name"], is_winner=False),
                f"{float(start_row['mean_cer']):.4f}",
                f"{float(start_row['mean_total_score']):.4f}",
                "다음 후보 생성 기준",
            ]
        ),
    ]
    for candidate in round_row["candidate_rows"]:
        assert isinstance(candidate, dict)
        is_winner = candidate["prompt_name"] == winner_name
        lines.append(
            md_table_row(
                [
                    "candidate",
                    format_prompt_name(candidate["prompt_name"], is_winner=is_winner),
                    f"{float(candidate['mean_cer']):.4f}",
                    f"{float(candidate['mean_total_score']):.4f}",
                    "winner" if is_winner else "",
                ]
            )
        )
    lines.extend(
        [
            "",
            "이 표의 뜻:",
            "- start는 그 라운드에서 후보를 생성할 때 기준이 된 프롬프트다.",
            "- 굵게 표시한 행이 그 라운드 winner다.",
            "",
        ]
    )
    return lines


def round_prompt_appendix(round_row: dict[str, object]) -> list[str]:
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


def sample_card(title: str, row: dict[str, object]) -> list[str]:
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
        "**New optimized OCR**",
        "",
        "```text",
        str(row["predicted_text"]),
        "```",
        "",
        f"이 사례의 뜻: baseline 대비 CER 변화는 `{row['delta']:+.4f}`다.",
        "",
    ]


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    seed_rows = read_csv(RUN_ROOT / "seed" / "seed_aggregate.csv")
    optimization_rows = read_csv(RUN_ROOT / "optimize" / "optimization_aggregate.csv")
    new_validation_rows = read_csv(RUN_ROOT / "validation" / "validation_aggregate.csv")
    prev_validation_rows = read_csv(PREV_RUN_ROOT / "validation" / "validation_aggregate.csv")

    baseline_eval = {row["sample_id"]: row for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")}
    final_eval = read_jsonl(RUN_ROOT / "validation" / "final" / "evaluations.jsonl")
    final_eval.sort(key=lambda row: row["sample_id"])
    sample_rows = []
    for row in final_eval:
        baseline_row = baseline_eval[row["sample_id"]]
        sample_rows.append(
            {
                **row,
                "baseline_text": baseline_row["predicted_text"],
                "baseline_cer": baseline_row["cer"],
                "delta": row["cer"] - baseline_row["cer"],
            }
        )
    sample_rows.sort(key=lambda row: row["delta"])

    round_rows = parse_rounds(optimization_rows)

    seed_chart = save_seed_chart(seed_rows)
    round_chart = save_round_chart(round_rows)
    validation_chart = save_validation_chart(prev_validation_rows, new_validation_rows)
    sample_delta_chart = save_sample_delta_chart(sample_rows)
    length_chart = save_prompt_length_chart(seed_rows, optimization_rows)

    best_seed = min(seed_rows, key=lambda row: float(row["mean_total_score"]) * -1)
    best_improvement = sample_rows[0]
    worst_regression = sample_rows[-1]
    dataset_examples = sample_rows[:2]

    previous_prompt = (PREV_RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    final_prompt = (RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    adopted_prompt = (RUN_ROOT / "adopted_prompt.txt").read_text(encoding="utf-8").strip()

    lines = [
        "# English-First Prompt Optimizer Report",
        "",
        "작성일: 2026-03-14",
        "",
        "## 1. 세 줄 요약",
        "",
        md_table_row(["질문", "답"]),
        md_table_row(["---", "---"]),
        md_table_row(["영어 우선 optimizer가 이전 optimizer보다 나아졌나?", "예. 같은 검증셋에서 optimized CER가 `0.4201 -> 0.3916`으로 개선됐다."]),
        md_table_row(["그래도 baseline을 이겼나?", "아니오. baseline CER `0.3824`보다 아직 조금 나빴다."]),
        md_table_row(["최종 채택 프롬프트는?", "baseline `Text Recognition:`"]),
        "",
        "이 표의 뜻:",
        "- 이번 개선은 완전 실패는 아니었다.",
        "- 이전 한국어 중심 optimizer보다 새 영어 우선 optimizer가 더 나았다.",
        "- 하지만 아직 baseline을 넘지는 못해서 실제 채택은 안 됐다.",
        "",
        "## 2. 이번 실험이 무엇을 바꿨는가",
        "",
        md_table_row(["항목", "내용"]),
        md_table_row(["---", "---"]),
        md_table_row(["데이터셋", "`AbdullahRian/Korean.OCR.Img.text.pair` fast subset"]),
        md_table_row(["dev / val", "`8 / 8`"]),
        md_table_row(["변경점", "seed prompt를 영어 중심으로 바꾸고, optimizer에 영어 우선 규칙과 실패 요약을 추가"]),
        md_table_row(["비교 대상", "기존 한국어 중심 optimized prompt vs 새 영어 우선 optimized prompt"]),
        "",
        "이 표의 뜻:",
        "- 이번 실험은 모델을 바꾼 것이 아니라 optimizer의 프롬프트 작성 전략을 바꾼 것이다.",
        "- 그래서 해석은 `더 좋은 OCR 지시문을 만들 수 있었는가`에 집중하면 된다.",
        "",
        "## 3. Seed Prompt 비교",
        "",
        f"![Seed chart](./{rel(seed_chart)})",
        "",
        md_table_row(["Prompt", "Mean CER", "Mean Total Score"]),
        md_table_row(["---", "---:", "---:"]),
    ]

    for row in seed_rows:
        lines.append(md_table_row([f"`{row['prompt_name']}`", f"{float(row['mean_cer']):.4f}", f"{float(row['mean_total_score']):.4f}"]))

    lines.extend(
        [
            "",
            "이 차트와 표의 뜻:",
            "- `P1`이 가장 좋은 seed였다.",
            "- 즉, 시작점으로는 길고 복잡한 프롬프트보다 짧은 영어 exact-transcription 프롬프트가 가장 안정적이었다.",
            "",
            "### Seed prompt 원문",
            "",
        ]
    )
    for row in seed_rows:
        lines.extend([f"#### `{row['prompt_name']}`", "", "```text", row["prompt_text"], "```", ""])

    lines.extend(
        [
            "## 4. Optimization 라운드 흐름",
            "",
            f"![Round chart](./{rel(round_chart)})",
            "",
            md_table_row(["Round", "Start", "Winner", "Winner CER", "Winner Score"]),
            md_table_row(["---", "---", "---", "---:", "---:"]),
        ]
    )

    for row in round_rows:
        lines.append(
            md_table_row(
                [
                    str(row["round"]),
                    f"`{row['start_name']}`",
                    f"`{row['winner_name']}`",
                    f"{row['winner_cer']:.4f}",
                    f"{row['winner_score']:.4f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트의 뜻:",
            "- dev set에서는 첫 seed winner `P1`이 사실상 끝까지 가장 강했다.",
            "- optimizer가 여러 변형을 만들었지만, 대부분 `비슷한 점수의 영어 규칙 프롬프트`로 수렴했다.",
            "",
            f"![Prompt length chart](./{rel(length_chart)})",
            "",
            "이 차트의 뜻:",
            "- 이번 subset에서는 프롬프트를 길게 쓴다고 점수가 좋아지지 않았다.",
            "- 짧고 직접적인 영어 프롬프트가 상위권에 남았다.",
            "",
        ]
    )

    for row in round_rows:
        lines.extend(round_candidate_table(row))

    lines.extend(
        [
            "## 5. Validation 비교",
            "",
            f"![Validation chart](./{rel(validation_chart)})",
            "",
            md_table_row(["Prompt", "Mean CER", "Mean Total Score"]),
            md_table_row(["---", "---:", "---:"]),
            md_table_row(["`baseline`", f"{float(new_validation_rows[0]['mean_cer']):.4f}", f"{float(new_validation_rows[0]['mean_total_score']):.4f}"]),
            md_table_row(["`old optimized`", f"{float(prev_validation_rows[1]['mean_cer']):.4f}", f"{float(prev_validation_rows[1]['mean_total_score']):.4f}"]),
            md_table_row(["`new optimized`", f"{float(new_validation_rows[1]['mean_cer']):.4f}", f"{float(new_validation_rows[1]['mean_total_score']):.4f}"]),
            "",
            "이 차트와 표의 뜻:",
            "- 새 optimizer는 이전 optimized prompt보다 분명히 나아졌다.",
            "- 하지만 baseline보다 CER가 `0.0092` 높아서, 최종 채택 기준은 넘지 못했다.",
            "",
            "### 최종 프롬프트 비교",
            "",
            "#### Previous optimized prompt",
            "",
            "```text",
            previous_prompt,
            "```",
            "",
            "#### New optimized prompt",
            "",
            "```text",
            final_prompt,
            "```",
            "",
            "#### Adopted prompt",
            "",
            "```text",
            adopted_prompt,
            "```",
            "",
            "## 6. 샘플별 영향",
            "",
            f"![Sample delta chart](./{rel(sample_delta_chart)})",
            "",
            md_table_row(["Sample", "Baseline CER", "New optimized CER", "Delta"]),
            md_table_row(["---", "---:", "---:", "---:"]),
        ]
    )

    for row in sample_rows:
        lines.append(
            md_table_row(
                [
                    f"`{row['sample_id']}`",
                    f"{row['baseline_cer']:.4f}",
                    f"{row['cer']:.4f}",
                    f"{row['delta']:+.4f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트의 뜻:",
            "- 8개 중 1개 샘플에서는 optimized가 더 좋아졌다.",
            "- 5개는 사실상 동일했고, 2개는 더 나빠졌다.",
            "- 즉, 새 optimizer는 `대부분 영향이 거의 없고 일부 샘플에서만 움직이는` 상태다.",
            "",
            "## 7. 데이터셋 대표 샘플 2개",
            "",
        ]
    )

    for index, row in enumerate(dataset_examples, start=1):
        image_path = ROOT / str(row["image_path"])
        lines.extend(
            [
                f"### 대표 샘플 {index}: `{row['sample_id']}`",
                "",
                f"![{row['sample_id']}]({Path('..') / image_path.relative_to(ROOT)})",
                "",
                "```text",
                str(row["reference_text"]),
                "```",
                "",
                "이 샘플의 뜻:",
                "- 이 데이터셋은 영수증 전체가 아니라, 한국어 line OCR에 가깝다.",
                "- 글자 모양이 난해하고 정답도 표준 문장이라기보다 원문 전사에 가깝다.",
                "",
            ]
        )

    lines.extend(
        [
            "## 8. 실제 비교 사례",
            "",
        ]
    )
    lines.extend(sample_card("Optimized가 더 나은 사례", best_improvement))
    lines.extend(sample_card("Optimized가 더 나쁜 사례", worst_regression))

    lines.extend(
        [
            "## 9. 해석",
            "",
            "이번 실험에서 확인된 것은 세 가지다.",
            "",
            "1. 영어 우선 optimizer는 이전 한국어 중심 optimizer보다 낫다.",
            "2. 하지만 이 fast subset에서는 baseline `Text Recognition:`이 여전히 가장 강하다.",
            "3. 긴 설명을 늘리기보다 짧고 직접적인 전사 규칙이 더 유망하다.",
            "",
            "다음으로 시도할 만한 방향은 이것이다.",
            "",
            "1. optimizer가 새 후보를 만들 때 `기존 baseline과 얼마나 다른지`를 더 강하게 제한한다.",
            "2. 실패 예시를 더 적게 주고, 대신 `정확히 어떤 글자 치환이 문제였는지`를 더 구조화해서 준다.",
            "3. line OCR과 receipt OCR을 섞지 말고, 데이터 유형별 optimizer 전략을 분리한다.",
            "",
            "## Appendix A. Round별 전체 프롬프트 원문",
            "",
            "이 부록의 뜻:",
            "- 각 라운드에서 실제로 어떤 문구들이 검토됐는지 문서만으로 추적할 수 있다.",
            "- winner뿐 아니라 탈락한 후보까지 다시 비교할 수 있다.",
            "",
        ]
    )

    for row in round_rows:
        lines.extend(round_prompt_appendix(row))

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
