"""A simple, offline interview-transcript grader.

It mimics the Gemini "transcript auditor" notebook: given a question and a
transcript, it returns the same JSON shape (overall score, AI-script detection,
and relevance/clarity/structure sub-scores). Instead of calling a language
model, it uses plain text heuristics, so the whole study runs without an API.

This is deliberately rough. Its job is to give the fusion and scoring stages a
realistic interview signal and to let us measure grade conformance against the
ground-truth tiers. Swap in the real Gemini stage in Colab for final numbers.
"""

from __future__ import annotations

import re

from ..datagen.answers import LLM_TELL_WORDS

# Words that suggest a vague, low-effort answer.
_VAGUE = ("good", "important", "interesting", "try", "normal", "things", "stuff", "nice")
# Words that suggest the answer drifted off the question.
_OFF_TOPIC = ("campus", "football", "travel", "city", "cafeteria", "friend", "famous")


def _count_hits(text: str, words) -> int:
    low = text.lower()
    return sum(low.count(w) for w in words)


def grade_transcript(question: str, transcript: str) -> dict:
    """Return a grade dict in the auditor-notebook JSON shape."""
    words = transcript.split()
    n_words = max(1, len(words))
    unique_ratio = len(set(w.lower() for w in words)) / n_words

    tell_hits = _count_hits(transcript, LLM_TELL_WORDS)
    vague_hits = _count_hits(transcript, _VAGUE)
    off_hits = _count_hits(transcript, _OFF_TOPIC)

    # AI-script suspicion: driven by tell-words and unnaturally polished, low
    # repetition text.
    suspicion = min(100, tell_hits * 22 + (15 if unique_ratio > 0.75 else 0))
    is_scripted = suspicion >= 50

    # Sub-scores on a 1-10 scale.
    relevance = 9 - min(8, off_hits * 3) - min(4, vague_hits * 2)
    clarity = 4 + (3 if unique_ratio > 0.6 else 0) + (2 if n_words > 45 else 0) - min(2, vague_hits)
    structure = 3 + (4 if n_words > 60 else 1) + (2 if unique_ratio > 0.65 else 0)
    relevance = int(max(1, min(10, relevance)))
    clarity = int(max(1, min(10, clarity)))
    structure = int(max(1, min(10, structure)))

    # Overall 0-100, weighting relevance most. A scripted answer keeps decent
    # quality scores but is capped and penalised so it cannot reach the top band.
    overall = (0.5 * relevance + 0.25 * clarity + 0.25 * structure) / 10 * 100
    if is_scripted:
        overall = min(overall, 72) - suspicion * 0.12
    overall = int(max(0, min(100, round(overall))))

    flags = [w for w in LLM_TELL_WORDS if w in transcript.lower()]
    return {
        "overall_score": overall,
        "ai_script_detection": {
            "is_likely_reading_llm_text": is_scripted,
            "suspicion_score": int(suspicion),
            "flags": flags,
        },
        "metrics": {
            "relevance_score": relevance,
            "clarity_score": clarity,
            "structure_score": structure,
        },
    }
