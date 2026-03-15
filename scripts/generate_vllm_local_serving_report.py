from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "runs" / "my-vllm-run-8"
DOCS_DIR = ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "009"
REPORT_PATH = DOCS_DIR / "009_vllm_local_glm_ocr_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def md_row(values: list[str]) -> str:
    return "| " + " | ".join(values) + " |"


def slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def prompt_anchor(name: str) -> str:
    return f"prompt-{slugify(name)}"


def prompt_link(name: str) -> str:
    return f"[`{name}`](#{prompt_anchor(name)})"


def image_link(source_path: str, label: str) -> str:
    return f"[{label}]({Path('..') / Path(source_path)})"


def save_seed_chart(seed_rows: list[dict[str, str]]) -> Path:
    names = [row["prompt_name"] for row in seed_rows]
    cer = [float(row["mean_cer"]) for row in seed_rows]
    score = [float(row["mean_total_score"]) for row in seed_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    colors = ["#4C78A8", "#59A14F", "#F28E2B", "#E15759"]
    axes[0].bar(names, cer, color=colors)
    axes[0].set_title("Seed Prompt CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(names, score, color=colors)
    axes[1].set_title("Seed Prompt Total Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "seed.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def parse_rounds(rows: list[dict[str, str]], candidates_per_round: int = 5) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    index = 0
    round_number = 1
    while index < len(rows):
        start = rows[index]
        candidates = rows[index + 1 : index + 1 + candidates_per_round]
        winner = max(candidates, key=lambda row: (float(row["mean_total_score"]), -len(row["prompt_text"])))
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
                "candidate_rows": candidates,
            }
        )
        index += 1 + candidates_per_round
        round_number += 1
    return parsed


def save_round_chart(round_rows: list[dict[str, object]], seed_best_row: dict[str, str]) -> Path:
    labels = ["Seed winner"] + [f"Round {row['round']}" for row in round_rows]
    cer = [float(seed_best_row["mean_cer"])] + [float(row["winner_cer"]) for row in round_rows]
    score = [float(seed_best_row["mean_total_score"])] + [float(row["winner_score"]) for row in round_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(labels, cer, marker="o", linewidth=2, color="#4C78A8")
    axes[0].set_title("Dev CER Trend")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(alpha=0.2)
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].plot(labels, score, marker="o", linewidth=2, color="#59A14F")
    axes[1].set_title("Dev Total Score Trend")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(alpha=0.2)
    axes[1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    path = ASSET_DIR / "rounds.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_validation_chart(validation_rows: list[dict[str, str]]) -> Path:
    labels = [row["prompt_name"] for row in validation_rows]
    cer = [float(row["mean_cer"]) for row in validation_rows]
    score = [float(row["mean_total_score"]) for row in validation_rows]
    repetition = [float(row["repetition_rate"]) for row in validation_rows]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    colors = ["#4C78A8", "#E15759"]

    axes[0].bar(labels, cer, color=colors)
    axes[0].set_title("Validation CER")
    axes[0].set_ylabel("Mean CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, score, color=colors)
    axes[1].set_title("Validation Total Score")
    axes[1].set_ylabel("Mean Total Score")
    axes[1].grid(axis="y", alpha=0.2)

    axes[2].bar(labels, repetition, color=colors)
    axes[2].set_title("Validation Repetition Rate")
    axes[2].set_ylabel("Rate")
    axes[2].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_latency_chart(validation_timing_rows: list[dict[str, str]]) -> Path:
    sample_rows = [
        row
        for row in validation_timing_rows
        if row["event_type"] == "sample_evaluation"
    ]
    baseline_rows = [row for row in sample_rows if row["prompt_name"] == "baseline"]
    final_rows = [row for row in sample_rows if row["prompt_name"] == "final"]

    labels = [row["sample_id"] for row in baseline_rows]
    baseline_sec = [float(row["request_seconds"]) for row in baseline_rows]
    final_sec = [float(row["request_seconds"]) for row in final_rows]

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))

    x = range(len(labels))
    width = 0.38
    axes[0].bar([i - width / 2 for i in x], baseline_sec, width=width, label="baseline", color="#4C78A8")
    axes[0].bar([i + width / 2 for i in x], final_sec, width=width, label="final", color="#E15759")
    axes[0].set_title("Validation Request Time by Sample")
    axes[0].set_ylabel("Request seconds")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(labels, rotation=20, ha="right")
    axes[0].grid(axis="y", alpha=0.2)
    axes[0].legend()

    axes[1].bar(
        ["baseline", "final"],
        [sum(baseline_sec) / len(baseline_sec), sum(final_sec) / len(final_sec)],
        color=["#4C78A8", "#E15759"],
    )
    axes[1].set_title("Validation Mean Request Time")
    axes[1].set_ylabel("Request seconds")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation_latency.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_sample_delta_chart(examples: list[dict]) -> Path:
    labels = [row["sample_id"] for row in examples]
    deltas = [row["cer"] - row["baseline_cer"] for row in examples]
    colors = ["#59A14F" if delta < 0 else "#E15759" for delta in deltas]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("Validation CER Delta per Sample (final - baseline)")
    ax.set_xlabel("CER delta")
    ax.grid(axis="x", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "sample_delta.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def copy_example_image(source_path: str, target_name: str) -> Path:
    source = (ROOT / source_path).resolve()
    target = ASSET_DIR / target_name
    shutil.copy2(source, target)
    return target


def prompt_block(title: str, name: str, prompt_text: str, *, add_anchor: bool) -> list[str]:
    lines = []
    if add_anchor:
        lines.append(f'<a id="{prompt_anchor(name)}"></a>')
    lines.extend([f"#### {title} `{name}`", "", "```text", prompt_text, "```", ""])
    return lines


def round_candidate_table(round_row: dict[str, object]) -> list[str]:
    lines = [
        f"### Round {round_row['round']} 전체 후보",
        "",
        md_row(["구분", "Prompt", "Mean CER (낮을수록 좋음)", "Mean Total Score (높을수록 좋음)", "Repetition Rate (낮을수록 좋음)", "비고"]),
        md_row(["---", "---", "---:", "---:", "---:", "---"]),
        md_row(
                [
                    "start",
                    prompt_link(str(round_row["start_name"])),
                    f"{float(round_row['start_cer']):.4f}",
                    f"{float(round_row['start_score']):.4f}",
                    "-",
                "기준 프롬프트",
            ]
        ),
    ]
    for candidate in round_row["candidate_rows"]:
        is_winner = candidate["prompt_name"] == round_row["winner_name"]
        linked = prompt_link(candidate["prompt_name"])
        label = f"**{linked}**" if is_winner else linked
        lines.append(
            md_row(
                [
                    "candidate",
                    label,
                    f"{float(candidate['mean_cer']):.4f}",
                    f"{float(candidate['mean_total_score']):.4f}",
                    f"{float(candidate['repetition_rate']):.2f}",
                    "winner" if is_winner else "",
                ]
            )
        )
    lines.extend(
        [
            "",
            "이 표의 뜻:",
            "- `start`는 그 라운드에서 후보를 만들 때 기준이 된 프롬프트다.",
            "- 굵게 표시한 행이 실제 winner다.",
            "",
        ]
    )
    return lines


def round_prompt_appendix(round_row: dict[str, object], anchored_names: set[str]) -> list[str]:
    start_name = str(round_row["start_name"])
    lines = [
        f"### Round {round_row['round']} 프롬프트 원문",
        "",
    ]
    if start_name not in anchored_names:
        lines.extend([f'<a id="{prompt_anchor(start_name)}"></a>'])
        anchored_names.add(start_name)
    lines.extend(
        [
        f"#### Start `{round_row['start_name']}`",
        "",
        "```text",
        str(round_row["start_prompt"]),
        "```",
        "",
        ]
    )
    for candidate in round_row["candidate_rows"]:
        suffix = " (winner)" if candidate["prompt_name"] == round_row["winner_name"] else ""
        candidate_name = candidate["prompt_name"]
        if candidate_name not in anchored_names:
            lines.extend([f'<a id="{prompt_anchor(candidate_name)}"></a>'])
            anchored_names.add(candidate_name)
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
    optimization_rows = read_csv(RUN_ROOT / "optimize" / "optimization_aggregate.csv")
    validation_rows = read_csv(RUN_ROOT / "validation" / "validation_aggregate.csv")
    validation_timing_rows = read_csv(RUN_ROOT / "validation" / "timing_summary.csv")
    final_report = read_json(RUN_ROOT / "final_report.json")

    round_rows = parse_rounds(optimization_rows)
    seed_best_row = max(seed_rows, key=lambda row: (float(row["mean_total_score"]), -len(row["prompt_text"])))

    baseline_row = next(row for row in validation_rows if row["prompt_name"] == "baseline")
    final_row = next(row for row in validation_rows if row["prompt_name"] == "final")

    sample_rows = []
    for example in final_report["examples"]:
        sample_rows.append(
            {
                **example,
                "baseline_cer": next(
                    float(row["cer"])
                    for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")
                    if row["sample_id"] == example["sample_id"]
                ),
            }
        )
    sample_rows.sort(key=lambda row: row["cer"] - row["baseline_cer"])

    best_example = sample_rows[0]
    worst_example = sample_rows[-1]
    copied_best_image = copy_example_image(best_example["image_path"], "best_example.jpg")
    copied_worst_image = copy_example_image(worst_example["image_path"], "worst_example.jpg")

    seed_chart = save_seed_chart(seed_rows)
    round_chart = save_round_chart(round_rows, seed_best_row)
    validation_chart = save_validation_chart(validation_rows)
    latency_chart = save_latency_chart(validation_timing_rows)
    sample_delta_chart = save_sample_delta_chart(sample_rows)

    optimized_prompt = (RUN_ROOT / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    adopted_prompt = (RUN_ROOT / "adopted_prompt.txt").read_text(encoding="utf-8").strip()
    anchored_names: set[str] = set()

    relative_improvement = float(final_report["relative_cer_improvement"]) * 100
    baseline_mean_request = sum(
        float(row["request_seconds"])
        for row in validation_timing_rows
        if row["event_type"] == "sample_evaluation" and row["prompt_name"] == "baseline"
    ) / 5
    final_mean_request = sum(
        float(row["request_seconds"])
        for row in validation_timing_rows
        if row["event_type"] == "sample_evaluation" and row["prompt_name"] == "final"
    ) / 5

    lines = [
        "# vLLM Local GLM-OCR Report",
        "",
        "작성일: 2026-03-15",
        "",
        "## 1. 세 줄 요약",
        "",
        md_row(["질문", "답"]),
        md_row(["---", "---"]),
        md_row(["로컬 `vllm` 서빙은 끝까지 안정적으로 돌았나?", "예. `my-vllm-run-8`이 seed, optimize, validation을 모두 완주했다."]),
        md_row(["최종 프롬프트는 baseline보다 좋아졌나?", f"예. validation mean CER가 `{float(baseline_row['mean_cer']):.4f} -> {float(final_row['mean_cer']):.4f}`로 개선됐다."]),
        md_row(["속도 목표도 만족했나?", "아니오. 로컬 GTX 1660 6GB에서는 일부 요청이 여전히 길고, 과거 Ollama 성공 구간 `12~16초/건`을 안정적으로 밑돌았다고 보긴 어렵다."]),
        "",
        "이 표의 뜻:",
        "- 이번 작업의 1차 목표였던 `안 죽고 끝까지 서빙하기`는 달성했다.",
        "- 프롬프트 최적화 품질도 baseline보다 좋아졌다.",
        "- 하지만 속도는 아직 넉넉하지 않아서, `빠른 로컬 OCR`로 보기는 어렵다.",
        "",
        "## 2. 이번 실험이 무엇을 검증했는가",
        "",
        md_row(["항목", "내용"]),
        md_row(["---", "---"]),
        md_row(["run", "`runs/my-vllm-run-8`"]),
        md_row(["서빙 방식", "로컬 `vllm` + `zai-org/GLM-OCR` + OpenAI 호환 `/v1/chat/completions`"]),
        md_row(["GPU", "GTX 1660 SUPER 6GB"]),
        md_row(["입력 전처리", "가장 긴 변을 `800px`로 제한"]),
        md_row(["컨텍스트 제한", "`--max-model-len 1024`"]),
        md_row(["dev / val", "`5 / 5`"]),
        "",
        "이 표의 뜻:",
        "- 이번 보고서는 모델 자체를 바꾼 것이 아니라, `로컬 vLLM 서빙이 실제로 버티는지`와 `그 상태에서 prompt optimization이 돌아가는지`를 본 것이다.",
        "- 이미지 크기와 컨텍스트 길이는 속도보다 생존성과 완주 가능성을 우선해 보수적으로 잡혔다.",
        "",
        "## 3. Seed 프롬프트 비교",
        "",
        f"![Seed chart](./{rel(seed_chart)})",
        "",
        md_row(["Prompt", "Mean CER (낮을수록 좋음)", "Mean Total Score (높을수록 좋음)", "Repetition Rate (낮을수록 좋음)"]),
        md_row(["---", "---:", "---:", "---:"]),
    ]

    for row in seed_rows:
        lines.append(
            md_row(
                [
                    prompt_link(row["prompt_name"]),
                    f"{float(row['mean_cer']):.4f}",
                    f"{float(row['mean_total_score']):.4f}",
                    f"{float(row['repetition_rate']):.2f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트와 표의 뜻:",
            "- `Mean CER`는 글자를 얼마나 틀렸는지 보여준다. 낮을수록 좋다.",
            "- `Mean Total Score`는 CER와 반복 패널티 등을 합친 종합 점수다. 높을수록 좋다.",
            "- `Repetition Rate`는 같은 내용을 반복 출력한 비율이다. 낮을수록 좋다.",
            f"- seed 단계에서는 `{seed_best_row['prompt_name']}`가 가장 나은 출발점이었다.",
            "- 이번 dev subset에서는 오히려 가장 짧은 baseline seed `P0`가 출발점으로 가장 강했다.",
            "",
            "### Seed 프롬프트 원문",
            "",
        ]
    )

    for row in seed_rows:
        add_anchor = row["prompt_name"] not in anchored_names
        if add_anchor:
            anchored_names.add(row["prompt_name"])
        lines.extend(prompt_block("Prompt", row["prompt_name"], row["prompt_text"], add_anchor=add_anchor))

    lines.extend(
        [
            "## 4. Optimization 라운드 흐름",
            "",
            f"![Round chart](./{rel(round_chart)})",
            "",
            md_row(["Round", "Start", "Winner", "Winner CER (낮을수록 좋음)", "Winner Score (높을수록 좋음)"]),
            md_row(["---", "---", "---", "---:", "---:"]),
        ]
    )

    for row in round_rows:
        lines.append(
            md_row(
                [
                    str(row["round"]),
                    prompt_link(str(row["start_name"])),
                    prompt_link(str(row["winner_name"])),
                    f"{float(row['winner_cer']):.4f}",
                    f"{float(row['winner_score']):.4f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트와 표의 뜻:",
            "- 왼쪽 선 그래프의 `CER`는 낮아질수록 좋다.",
            "- 오른쪽 선 그래프의 `Score`는 높아질수록 좋다.",
            "- dev set에서는 1라운드에서 CER가 꽤 개선됐고, 그 다음부터는 비슷한 문장 구조 안에서 미세 조정이 반복됐다.",
            "- 즉, 이번 optimizer는 완전히 새로운 지시문을 찾기보다 `짧은 영어 규칙 프롬프트`를 조금씩 다듬는 방향으로 수렴했다.",
            "",
        ]
    )

    for row in round_rows:
        lines.extend(round_candidate_table(row))

    lines.extend(
        [
            "## 5. Validation 품질 비교",
            "",
            f"![Validation chart](./{rel(validation_chart)})",
            "",
            md_row(["Prompt", "Mean CER (낮을수록 좋음)", "Mean Total Score (높을수록 좋음)", "Repetition Rate (낮을수록 좋음)"]),
            md_row(["---", "---:", "---:", "---:"]),
            md_row(
                [
                    "`baseline`",
                    f"{float(baseline_row['mean_cer']):.4f}",
                    f"{float(baseline_row['mean_total_score']):.4f}",
                    f"{float(baseline_row['repetition_rate']):.2f}",
                ]
            ),
            md_row(
                [
                    "`final`",
                    f"{float(final_row['mean_cer']):.4f}",
                    f"{float(final_row['mean_total_score']):.4f}",
                    f"{float(final_row['repetition_rate']):.2f}",
                ]
            ),
            "",
            "이 차트와 표의 뜻:",
            "- 첫 번째 막대의 `CER`는 낮을수록 좋다.",
            "- 두 번째 막대의 `Total Score`는 높을수록 좋다.",
            "- 세 번째 막대의 `Repetition Rate`는 낮을수록 좋다.",
            f"- validation mean CER는 약 `{relative_improvement:.1f}%` 개선됐다.",
            "- repetition rate도 `0.6 -> 0.4`로 줄어서, baseline에서 보이던 반복 출력이 조금 줄었다.",
            "- 다만 absolute CER가 아직 높아서, 품질이 좋아졌다고 해도 실사용 관점에선 여전히 거칠다.",
            "",
            "### 최종 프롬프트 비교",
            "",
        ]
    )

    for title, name, text in [
        ("Baseline", "baseline", "Text Recognition:"),
        ("Optimized final", "final", optimized_prompt),
        ("Adopted", "adopted", adopted_prompt),
    ]:
        add_anchor = name not in anchored_names
        if add_anchor:
            anchored_names.add(name)
        lines.extend(prompt_block(title, name, text, add_anchor=add_anchor))

    lines.extend(
        [
            "## 6. Validation 속도 비교",
            "",
            f"![Validation latency chart](./{rel(latency_chart)})",
            "",
            md_row(["Prompt", "Mean request seconds (낮을수록 좋음)", "비고"]),
            md_row(["---", "---:", "---"]),
            md_row(["`baseline`", f"{baseline_mean_request:.2f}", "긴 응답을 자주 생성하며 매우 느렸다"]),
            md_row(["`final`", f"{final_mean_request:.2f}", "평균은 크게 줄었지만 여전히 빠르다고 보긴 어렵다"]),
            "",
            "이 차트와 표의 뜻:",
            "- 이 섹션의 `request seconds`는 낮을수록 좋다.",
            "- 왼쪽 그래프는 샘플별 요청 시간이고, 오른쪽 그래프는 평균 요청 시간이다.",
            "- 이번 validation에서는 optimized prompt가 baseline보다 훨씬 짧고 안정적으로 끝났다.",
            "- 하지만 이 결과를 `로컬 vLLM이 충분히 빠르다`로 해석하면 안 된다.",
            "- 과거 Ollama 성공 로그 기준 `12~16초/건`과 비교하면, 이번 run은 일부 요청이 여전히 그 구간을 넘었다.",
            "",
        ]
    )

    lines.extend(
        [
            "## 7. 샘플별 영향",
            "",
            f"![Sample delta chart](./{rel(sample_delta_chart)})",
            "",
            md_row(["Sample", "Baseline CER (낮을수록 좋음)", "Final CER (낮을수록 좋음)", "Delta (음수면 개선)"]),
            md_row(["---", "---:", "---:", "---:"]),
        ]
    )
    for row in sample_rows:
        lines.append(
            md_row(
                [
                    image_link(row["image_path"], f"`{row['sample_id']}`"),
                    f"{row['baseline_cer']:.4f}",
                    f"{row['cer']:.4f}",
                    f"{row['cer'] - row['baseline_cer']:+.4f}",
                ]
            )
        )

    lines.extend(
        [
            "",
            "이 차트의 뜻:",
            "- 여기서 `Delta`는 `final - baseline`이다.",
            "- 그래서 막대가 왼쪽, 즉 음수일수록 final prompt가 더 좋아진 것이다.",
            "- 5개 validation 샘플 모두에서 final prompt가 baseline보다 같거나 더 좋았다.",
            "- 다만 개선폭이 큰 샘플도 여전히 CER가 높아서, 문서 OCR 자체가 이 환경에선 어려운 편이다.",
            "",
            "## 8. 대표 비교 사례",
            "",
            f"### 더 나은 사례: `{best_example['sample_id']}`",
            "",
            f"![best example](./{rel(copied_best_image)})",
            "",
            f"원본 이미지: {image_link(best_example['image_path'], 'dataset image')}",
            "",
            "**Reference**",
            "",
            "```text",
            str(best_example["reference_text"]),
            "```",
            "",
            "**Baseline OCR**",
            "",
            "```text",
            next(
                row["predicted_text"]
                for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")
                if row["sample_id"] == best_example["sample_id"]
            ),
            "```",
            "",
            "**Final OCR**",
            "",
            "```text",
            str(best_example["predicted_text"]),
            "```",
            "",
            f"이 사례의 뜻: CER 변화는 `{best_example['cer'] - best_example['baseline_cer']:+.4f}`다.",
            "",
            f"### 여전히 어려운 사례: `{worst_example['sample_id']}`",
            "",
            f"![worst example](./{rel(copied_worst_image)})",
            "",
            f"원본 이미지: {image_link(worst_example['image_path'], 'dataset image')}",
            "",
            "**Reference**",
            "",
            "```text",
            str(worst_example["reference_text"]),
            "```",
            "",
            "**Baseline OCR**",
            "",
            "```text",
            next(
                row["predicted_text"]
                for row in read_jsonl(RUN_ROOT / "validation" / "baseline" / "evaluations.jsonl")
                if row["sample_id"] == worst_example["sample_id"]
            ),
            "```",
            "",
            "**Final OCR**",
            "",
            "```text",
            str(worst_example["predicted_text"]),
            "```",
            "",
            f"이 사례의 뜻: improvement가 가장 작은 샘플도 여전히 CER는 `{worst_example['cer']:.4f}`로 높다.",
            "",
            "## 9. 해석",
            "",
            "이번 실험에서 확정적으로 말할 수 있는 것은 세 가지다.",
            "",
            "1. `vllm` 로컬 서빙은 이 환경에서 `ollama`보다 적어도 더 안정적으로 끝까지 돈다.",
            "2. prompt optimization은 baseline보다 더 나은 지시문을 실제로 찾았다.",
            "3. 하지만 GTX 1660 SUPER 6GB에서는 속도 여유가 작아서, 로컬 운영 환경으로는 아직 타이트하다.",
            "",
            "## 10. 다음 단계",
            "",
            md_row(["제안", "이유"]),
            md_row(["---", "---"]),
            md_row(["현재 `800px / max-model-len 1024`를 운영 기본값으로 고정", "이번 조합이 처음으로 완주 가능한 조합이었다"]),
            md_row(["속도 비교 실험은 prompt 변화보다 입력 크기와 문서 유형별로 따로 수행", "지금 병목은 프롬프트보다 추론 자원 한계에 더 가깝다"]),
            md_row(["보고서 후속판에서는 더 큰 GPU나 외부 API와의 비교 추가", "이번 보고서는 로컬 vLLM 단일 환경 기록에 가깝다"]),
            "",
            "## 부록 A. Round별 전체 프롬프트 원문",
            "",
            "이 부록의 뜻:",
            "- winner만이 아니라 탈락한 후보까지 문서 안에서 바로 추적할 수 있다.",
            "- 다음 실험에서 어떤 문구가 이미 시도됐는지 다시 확인하기 쉽다.",
            "",
        ]
    )

    for row in round_rows:
        lines.extend(round_prompt_appendix(row, anchored_names))

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
