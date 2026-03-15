from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN_V3 = ROOT / "runs" / "korean-ocr-img-text-pair-heldout-v3" / "validation" / "validation_aggregate.csv"
RUN_V5 = ROOT / "runs" / "korean-ocr-img-text-pair-heldout-v5" / "validation" / "validation_aggregate.csv"
DOCS_DIR = ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets" / "008"
REPORT_PATH = DOCS_DIR / "008_non_korean_suppression_followup.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    return path.relative_to(DOCS_DIR).as_posix()


def save_validation_chart(v3: list[dict[str, str]], v5: list[dict[str, str]]) -> Path:
    labels = ["v3 baseline", "v3 optimized", "v5 baseline", "v5 optimized"]
    cer = [
        float(v3[0]["mean_cer"]),
        float(v3[1]["mean_cer"]),
        float(v5[0]["mean_cer"]),
        float(v5[1]["mean_cer"]),
    ]
    score = [
        float(v3[0]["mean_total_score"]),
        float(v3[1]["mean_total_score"]),
        float(v5[0]["mean_total_score"]),
        float(v5[1]["mean_total_score"]),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(labels, cer, color=["#BAB0AC", "#E15759", "#9C755F", "#59A14F"])
    axes[0].set_title("Validation CER")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, score, color=["#BAB0AC", "#E15759", "#9C755F", "#59A14F"])
    axes[1].set_title("Validation Total Score")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "validation_compare.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def save_stability_chart(v3: list[dict[str, str]], v5: list[dict[str, str]]) -> Path:
    labels = ["v3 optimized", "v5 optimized"]
    non_korean = [float(v3[1]["non_korean_rate"]), float(v5[1]["non_korean_rate"])]
    token_f1 = [float(v3[1]["mean_token_f1"]), float(v5[1]["mean_token_f1"])]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    axes[0].bar(labels, non_korean, color=["#E15759", "#59A14F"])
    axes[0].set_title("Non-Korean Rate")
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(labels, token_f1, color=["#E15759", "#59A14F"])
    axes[1].set_title("Mean Token F1")
    axes[1].grid(axis="y", alpha=0.2)

    fig.tight_layout()
    path = ASSET_DIR / "stability_compare.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    v3 = read_csv(RUN_V3)
    v5 = read_csv(RUN_V5)

    validation_chart = save_validation_chart(v3, v5)
    stability_chart = save_stability_chart(v3, v5)

    v5_prompt = (ROOT / "runs" / "korean-ocr-img-text-pair-heldout-v5" / "optimize" / "final_prompt.txt").read_text(
        encoding="utf-8"
    ).strip()

    lines = [
        "# Non-Korean Suppression Follow-up",
        "",
        "작성일: 2026-03-15",
        "",
        "## 1. 한눈에 보는 결론",
        "",
        "| 질문 | 답 |",
        "|---|---|",
        "| placeholder 금지와 script-substitution 금지가 효과가 있었나? | 예 |",
        f"| optimized non-Korean rate | `6.25% -> 0.00%` |",
        f"| optimized normalized CER | `{float(v3[1]['mean_cer']):.4f} -> {float(v5[1]['mean_cer']):.4f}` |",
        "",
        "이 표의 뜻:",
        "- 이전 v3에서는 optimized prompt가 한자 대체를 일으켜 채택에 실패했다.",
        "- 이번 v5에서는 그 문제가 사라졌고 CER도 더 좋아졌다.",
        "",
        "## 2. 비교 차트",
        "",
        f"![Validation compare](./{rel(validation_chart)})",
        "",
        "이 차트의 뜻:",
        "- v5 optimized는 v3 optimized보다 CER와 total score가 모두 좋아졌다.",
        "",
        f"![Stability compare](./{rel(stability_chart)})",
        "",
        "이 차트의 뜻:",
        "- 핵심 변화는 non-Korean rate가 0으로 내려간 것이다.",
        "- 즉, 마지막 수정은 실제 문제 원인을 제대로 겨냥했다.",
        "",
        "## 3. 최종 optimized prompt",
        "",
        "```text",
        v5_prompt,
        "```",
        "",
        "## 4. 해석",
        "",
        "이번 후속 실험으로 확인된 것은 두 가지다.",
        "",
        "1. `[unclear]` placeholder 금지만으로는 부족했고, `중국어/한자 대체 금지`를 명시해야 했다.",
        "2. 그 규칙을 넣자 stability 문제는 해결됐고, CER도 함께 좋아졌다.",
        "",
        "아직 baseline이 채택된 이유는 PRD 규칙이 `CER 개선 + 안정성 지표 개선`을 동시에 요구하는데, baseline도 이미 안정성 지표가 0이라 더 낮출 값이 없기 때문이다.",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
