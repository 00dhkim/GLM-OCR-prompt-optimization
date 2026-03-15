from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def save_seed_chart(rows: list[dict[str, str]]) -> Path:
    labels = [row["prompt_name"] for row in rows]
    cer = [float(row["mean_cer"]) for row in rows]
    score = [float(row["mean_total_score"]) for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(labels, cer, color=["#4E79A7", "#59A14F", "#F28E2B", "#E15759"])
    axes[0].set_title("Seed Prompt CER")
    axes[0].set_ylabel("Mean normalized CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, score, color=["#4E79A7", "#59A14F", "#F28E2B", "#E15759"])
    axes[1].set_title("Seed Prompt Total Score")
    axes[1].set_ylabel("Mean total score")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "seed.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_validation_chart(rows: list[dict[str, str]]) -> Path:
    labels = [row["prompt_name"] for row in rows]
    cer = [float(row["mean_cer"]) for row in rows]
    score = [float(row["mean_total_score"]) for row in rows]
    repetition = [float(row["repetition_rate"]) for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].bar(labels, cer, color=["#76B7B2", "#E15759"])
    axes[0].set_title("Validation CER")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, score, color=["#76B7B2", "#E15759"])
    axes[1].set_title("Validation Total Score")
    axes[1].grid(axis="y", alpha=0.2)

    axes[2].bar(labels, repetition, color=["#76B7B2", "#E15759"])
    axes[2].set_title("Repetition Rate")
    axes[2].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_sample_delta_chart(samples: list[dict[str, object]]) -> Path:
    labels = [row["sample_id"] for row in samples]
    deltas = [float(row["delta"]) for row in samples]
    colors = ["#59A14F" if delta < 0 else "#E15759" for delta in deltas]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("Sample-level CER Delta (Final - Baseline)")
    ax.set_xlabel("CER delta")
    ax.grid(axis="x", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "sample_delta.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def md_row(values: list[str]) -> str:
    return "| " + " | ".join(values) + " |"


def shorten(text: str, limit: int = 140) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def prompt_block(title: str, text: str) -> list[str]:
    return [title, "", "```text", text, "```", ""]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs" / "korie-ocr-vllm-smoke")
    parser.add_argument("--doc-number", default="009")
    parser.add_argument("--report-name", default="arize_ax_vllm_korie_smoke_report")
    parser.add_argument("--title", default="Arize AX VLLM KORIE Smoke Report")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_root = args.run_root if args.run_root.is_absolute() else (ROOT / args.run_root)
    asset_dir = DOCS_DIR / "assets" / args.doc_number
    report_path = DOCS_DIR / f"{args.doc_number}_{args.report_name}.md"

    asset_dir.mkdir(parents=True, exist_ok=True)

    seed_rows = read_csv(run_root / "seed" / "seed_aggregate.csv")
    validation_rows = read_csv(run_root / "validation" / "validation_aggregate.csv")
    report = read_json(run_root / "final_report.json")

    baseline_eval = {
        row["sample_id"]: row for row in read_jsonl(run_root / "validation" / "baseline" / "evaluations.jsonl")
    }
    final_eval = read_jsonl(run_root / "validation" / "final" / "evaluations.jsonl")

    samples: list[dict[str, object]] = []
    for row in final_eval:
        baseline = baseline_eval[row["sample_id"]]
        samples.append(
            {
                "sample_id": row["sample_id"],
                "reference_text": row["reference_text"],
                "baseline_text": baseline["predicted_text"],
                "final_text": row["predicted_text"],
                "baseline_cer": baseline["cer"],
                "final_cer": row["cer"],
                "delta": row["cer"] - baseline["cer"],
            }
        )
    samples.sort(key=lambda row: float(row["delta"]))

    global ASSET_DIR
    ASSET_DIR = asset_dir
    seed_chart = save_seed_chart(seed_rows)
    validation_chart = save_validation_chart(validation_rows)
    sample_delta_chart = save_sample_delta_chart(samples)

    best_seed = max(seed_rows, key=lambda row: float(row["mean_total_score"]))
    best_case = samples[0]
    median_case = samples[len(samples) // 2]
    worst_case = samples[-1]

    rounds: list[dict[str, object]] = []
    for round_dir in sorted((run_root / "optimize").glob("round_*")):
        summary = read_json(round_dir / "round_summary.json")
        rounds.append(summary)

    final_prompt = (run_root / "optimize" / "final_prompt.txt").read_text(encoding="utf-8").strip()
    adopted_prompt = (run_root / "adopted_prompt.txt").read_text(encoding="utf-8").strip()
    baseline_prompt = "Text Recognition:"

    lines = [
        f"# {args.title}",
        "",
        "작성일: 2026-03-15",
        "",
        "## 1. 한눈에 보는 결론",
        "",
        md_row(["질문", "답"]),
        md_row(["---", "---"]),
        md_row(["실제 vLLM GLM-OCR로 smoke benchmark를 돌렸나?", f"예. `{run_root.relative_to(ROOT).as_posix()}`를 사용했다."]),
        md_row(["Arize AX 방식의 prompt learning이 baseline을 이겼나?", "실험 결과를 기준으로 판단했다."]),
        md_row(["왜 이런 결과가 나왔나?", "round별 후보와 reject reason을 함께 보면 확인할 수 있다."]),
        md_row(["이번 실험의 핵심 교훈", "OCR-safe guardrail이 실제로 장문 prompt drift를 막는지 보는 것이다."]),
        "",
        "이 표의 뜻:",
        "- 이번 smoke run은 코드 경로가 실제 vLLM OCR로 끝까지 동작했는지 확인하는 작은 실험이다.",
        "- 이 보고서는 1-round smoke 결과를 빠르게 검증하기 위한 문서다.",
        "",
        "## 2. Seed prompt 비교",
        "",
        f"![Seed chart](./{rel(seed_chart)})",
        "",
        "이 차트의 뜻:",
        f"- 가장 좋은 seed는 `{best_seed['prompt_name']}`였고 score는 `{float(best_seed['mean_total_score']):.4f}`였다.",
        f"- baseline `P0`보다 `P1`이 훨씬 안정적이어서 optimizer의 출발점으로 적절했다.",
        "",
        "## 3. Validation 결과",
        "",
        f"![Validation chart](./{rel(validation_chart)})",
        "",
        "이 차트의 뜻:",
        f"- baseline validation CER는 `{report['baseline']['mean_cer']:.4f}`였다.",
        f"- final prompt validation CER는 `{report['final']['mean_cer']:.4f}`였다.",
        f"- 반복률은 `{report['baseline']['repetition_rate']:.2%} -> {report['final']['repetition_rate']:.2%}`였다.",
        "",
        "## 4. 샘플별 차이",
        "",
        f"![Sample delta](./{rel(sample_delta_chart)})",
        "",
        "이 차트의 뜻:",
        "- 초록색은 optimized가 baseline보다 나았던 샘플이다.",
        "- 빨간색은 optimized가 더 나빴던 샘플이다.",
        "- 이 차트로 guardrail 이후에도 validation이 실제로 나아졌는지 한눈에 볼 수 있다.",
        "",
        "## 5. 대표 사례",
        "",
        "### 5.1 가장 덜 나빠진 샘플",
        "",
        md_row(["항목", "내용"]),
        md_row(["---", "---"]),
        md_row(["sample_id", str(best_case["sample_id"])]),
        md_row(["baseline CER", f"{float(best_case['baseline_cer']):.4f}"]),
        md_row(["final CER", f"{float(best_case['final_cer']):.4f}"]),
        md_row(["delta", f"{float(best_case['delta']):.4f}"]),
        "",
        "Reference:",
        f"`{best_case['reference_text']}`",
        "",
        "Baseline output:",
        f"`{best_case['baseline_text']}`",
        "",
        "Final output:",
        f"`{best_case['final_text']}`",
        "",
        "### 5.2 중간 정도로 망가진 샘플",
        "",
        md_row(["항목", "내용"]),
        md_row(["---", "---"]),
        md_row(["sample_id", str(median_case["sample_id"])]),
        md_row(["baseline CER", f"{float(median_case['baseline_cer']):.4f}"]),
        md_row(["final CER", f"{float(median_case['final_cer']):.4f}"]),
        md_row(["delta", f"{float(median_case['delta']):.4f}"]),
        "",
        "Reference:",
        f"`{median_case['reference_text']}`",
        "",
        "Baseline output:",
        f"`{median_case['baseline_text']}`",
        "",
        "Final output:",
        f"`{median_case['final_text']}`",
        "",
        "### 5.3 가장 크게 무너진 샘플",
        "",
        md_row(["항목", "내용"]),
        md_row(["---", "---"]),
        md_row(["sample_id", str(worst_case["sample_id"])]),
        md_row(["baseline CER", f"{float(worst_case['baseline_cer']):.4f}"]),
        md_row(["final CER", f"{float(worst_case['final_cer']):.4f}"]),
        md_row(["delta", f"{float(worst_case['delta']):.4f}"]),
        "",
        "Reference:",
        f"`{worst_case['reference_text']}`",
        "",
        "Baseline output:",
        f"`{worst_case['baseline_text']}`",
        "",
        "Final output:",
        f"`{worst_case['final_text']}`",
        "",
        "## 6. Round별 전체 후보",
        "",
        "이 섹션의 뜻:",
        "- round마다 어떤 시작 prompt가 있었고, 어떤 candidate가 만들어졌는지 숨기지 않고 남긴다.",
        "- 이 표는 어떤 후보가 reject됐고 어떤 짧은 후보가 살아남았는지 보여준다.",
        "",
    ]

    for summary in rounds:
        lines.extend(
            [
                f"### Round {summary['round_index']}",
                "",
                "Start prompt:",
                f"`{summary['starting_prompt']['name']}`",
                "",
                md_row(["candidate", "winner", "rejected", "mean_total_score", "mean_cer", "prompt preview"]),
                md_row(["---", "---", "---", "---", "---", "---"]),
            ]
        )
        candidate_aggregates = summary["candidate_aggregates"]
        winner_name = summary["selected_candidate"]["name"]
        rejected = summary.get("rejected_candidates", {})
        for row in candidate_aggregates:
            name = row["prompt_name"]
            winner = "**yes**" if name == winner_name else ""
            reject_reason = ", ".join(rejected.get(name, []))
            lines.append(
                md_row(
                    [
                        name,
                        winner,
                        reject_reason,
                        f"{float(row['mean_total_score']):.4f}",
                        f"{float(row['mean_cer']):.4f}",
                        shorten(row["prompt_text"]),
                    ]
                )
            )
        lines.append("")

    lines.extend(
        [
            "## 7. Prompt 원문",
            "",
            "baseline은 짧고 단순했다.",
            "",
        ]
    )
    lines.extend(prompt_block("### Baseline prompt", baseline_prompt))
    lines.extend(
        [
            "이번 run에서 실제 채택된 prompt는 아래와 같다.",
            "",
        ]
    )
    lines.extend(prompt_block("### Adopted prompt", adopted_prompt))
    lines.extend(
        [
            "optimizer가 만든 최종 후보 prompt는 아래와 같다.",
            "",
        ]
    )
    lines.extend(prompt_block("### Final optimized prompt", final_prompt))
    lines.extend(
        [
            "## 8. Arize AX 연결 상태",
            "",
            "- 현재 코드 기준으로 tracing은 `arize-otel`을 통해 Arize AX 공식 경로를 사용한다.",
            "- 반면 Phoenix prompt/dataset REST client는 `PHOENIX_BASE_URL`이 확인되지 않으면 시도하지 않는다.",
            f"- report JSON의 reject summary는 `{report.get('rejected_reason_summary', {})}`다.",
            "- 이번 환경에서는 AX tracing 기본 경로는 정리됐지만, Phoenix app API base URL은 아직 확정하지 못했다.",
            "",
            "## 9. 해석",
            "",
            "이번 결과는 prompt learning SDK가 나쁘다는 뜻이 아니다.",
            "문제는 OCR 태스크에서 system prompt가 너무 길어지면 모델이 전사기보다 instruction follower처럼 반응하면서 출력이 무너질 수 있다는 점이다.",
            "즉 다음 단계는 SDK를 빼는 것이 아니라, OCR용 guardrail을 더 강하게 넣는 것이다.",
            "",
            "1. optimized prompt 길이에 더 강한 hard cap을 넣는다.",
            "2. `YOUR NEW PROMPT:` 같은 scaffolding text를 후보에서 제거하는 sanitizer를 넣는다.",
            "3. repetition과 overlong output을 candidate selection 단계에서 더 강하게 벌점 준다.",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
