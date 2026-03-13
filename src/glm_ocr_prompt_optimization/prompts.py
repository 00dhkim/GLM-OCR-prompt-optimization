from __future__ import annotations

from .models import PromptCandidate


def default_seed_prompts() -> list[PromptCandidate]:
    return [
        PromptCandidate(name="P0", text="Text Recognition:", rationale="Baseline prompt."),
        PromptCandidate(
            name="P1",
            text="Text Recognition:\n보이는 글자를 한국어 중심으로 그대로 전사하라.",
            rationale="Adds explicit Korean transcription guidance.",
        ),
        PromptCandidate(
            name="P2",
            text=(
                "Text Recognition:\n"
                "보이는 글자를 그대로 전사하라.\n"
                "번역하지 마라.\n"
                "추정해서 보정하지 마라."
            ),
            rationale="Adds no-translation and no-guess constraints.",
        ),
        PromptCandidate(
            name="P3",
            text=(
                "Text Recognition:\n"
                "보이는 글자를 한국어 중심으로 그대로 전사하라.\n"
                "번역하지 마라.\n"
                "확실하지 않은 글자도 임의 보정하지 마라.\n"
                "같은 문자열을 반복 생성하지 마라.\n"
                "인식이 어려우면 반복하지 말고 보이는 범위까지만 출력하라."
            ),
            rationale="Adds conservative uncertainty handling and repetition suppression.",
        ),
    ]
