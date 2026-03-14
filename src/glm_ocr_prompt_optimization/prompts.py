from __future__ import annotations

from .models import PromptCandidate


def default_seed_prompts() -> list[PromptCandidate]:
    return [
        PromptCandidate(name="P0", text="Text Recognition:", rationale="Baseline prompt."),
        PromptCandidate(
            name="P1",
            text="Text Recognition:\nTranscribe all visible text exactly as it appears.",
            rationale="Adds a short exact-transcription rule in English.",
        ),
        PromptCandidate(
            name="P2",
            text=(
                "Text Recognition:\n"
                "Transcribe only the visible text.\n"
                "Output plain text only.\n"
                "Do not translate, correct, or guess."
            ),
            rationale="Adds explicit no-translation, no-correction, and no-guess rules.",
        ),
        PromptCandidate(
            name="P3",
            text=(
                "Text Recognition:\n"
                "Read the image and transcribe only the visible text in plain text.\n"
                "Preserve the observed reading order and line breaks when clear.\n"
                "Do not translate, explain, normalize, or guess missing characters.\n"
                "If part of the text is unclear, keep only the visible portion.\n"
                "Do not repeat text."
            ),
            rationale="Adds reading-order, uncertainty, and repetition control in English.",
        ),
    ]
