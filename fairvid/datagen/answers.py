"""Layer 3: interview answer transcripts, each tagged with a quality label.

For every question we give an applicant, we pick a quality tier and write an
answer that matches it. The tier is the ground truth: later we check whether the
grading stage's score lands in the band we expect for that tier, and whether its
AI-script detector flags the answers we wrote to look AI-generated.

Tiers:
  strong      - on-topic, specific, natural phrasing
  weak        - short, vague, generic
  off_topic   - fluent but doesn't answer the question
  ai_scripted - polished and stuffed with classic LLM "tell" words

The text is built from templates, not a real language model, so generation is
fast, offline, and reproducible. It is good enough to exercise the grading
stage; swapping in a real LLM later only changes this file.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TIERS = ("strong", "weak", "off_topic", "ai_scripted")

# Expected grade band (0-100) for each tier. Calibrated to the offline grader
# in pipeline/grader.py. Used to check that the grader lands in the right band.
TIER_SCORE_BAND = {
    "strong": (68, 100),
    "weak": (32, 62),
    "off_topic": (18, 52),
    "ai_scripted": (40, 72),  # reads well, but should be flagged as scripted
}

# The "tell" words the grading prompt explicitly looks for. We plant these in
# the ai_scripted answers so the detector has something genuine to catch.
LLM_TELL_WORDS = (
    "delve", "underscore", "pivotal role", "tapestry", "multifaceted",
    "holistic approach", "leverage", "furthermore", "moreover", "intricate",
)

# Pools are kept large and varied so that two answers in the same tier are not
# identical: the grader then sees genuine variation rather than a constant.
_STRONG = (
    "In my final-year project I worked directly on this and learned a lot.",
    "From hands-on experience, I would start by nailing down the fundamentals.",
    "I ran into exactly this problem during an internship last summer.",
    "We measured the trade-offs, iterated on prototypes, and documented what failed.",
    "I focused on the data first, validated my assumptions, then refined the design.",
    "Concretely, I compared two approaches and picked the one with better margins.",
    "I tested the result under load and recorded where it broke and why.",
    "A specific example was rebuilding the sensor calibration from scratch.",
    "I reviewed three recent papers and applied one method to my own dataset.",
    "The hardest part was debugging the edge cases, which taught me to be rigorous.",
)
_WEAK = (
    "I think it is important and I would try my best.",
    "It is a good topic and I have read a little about it.",
    "Yes, this is interesting and I want to learn more.",
    "I would do the normal steps and see what happens.",
    "It is a nice subject and many people study it.",
    "I am not sure, but I would figure things out somehow.",
    "It depends on the situation, I guess.",
)
_OFF_TOPIC = (
    "Honestly, what excites me most is the campus life and the city.",
    "I really enjoy football and travelling on the weekends.",
    "My friend studied here and said the cafeteria is great.",
    "The program is famous, so I thought I would apply.",
    "I like the location and the weather seems pleasant.",
    "There are many clubs and societies that look fun.",
)
_AI_PHRASES = (
    "It is essential to delve into the multifaceted dimensions of this question.",
    "Furthermore, a holistic approach lets us leverage emerging paradigms.",
    "Moreover, this underscores the pivotal role of innovation.",
    "This intricate tapestry of considerations ultimately shapes outcomes.",
    "We must underscore the multifaceted and intricate nature of the challenge.",
    "Furthermore, leveraging synergies plays a pivotal role moving forward.",
)
_POOLS = {"strong": _STRONG, "weak": _WEAK, "off_topic": _OFF_TOPIC, "ai_scripted": _AI_PHRASES}


@dataclass
class AnswerLabel:
    question_index: int
    question: str
    tier: str
    expected_score_low: int
    expected_score_high: int
    is_ai_scripted: bool
    word_count: int


def _target_words(time_seconds: int, rng: np.random.Generator) -> int:
    """Roughly 2.7 words/sec (~160 wpm), with ±15% jitter so lengths vary."""
    base = max(20, int(time_seconds * 2.7))
    return int(base * rng.uniform(0.85, 1.15))


def _compose(pool, target_words: int, rng: np.random.Generator) -> str:
    """Build an answer by sampling varied sentences from the pool until the
    target length is reached. Avoids repeating the same sentence back to back."""
    sentences, count, last = [], 0, None
    while count < target_words:
        choice = str(rng.choice(pool))
        if choice == last and len(pool) > 1:
            continue
        sentences.append(choice)
        last = choice
        count += len(choice.split())
    return " ".join(sentences)


def _pick_tier(merit_score: float, rng: np.random.Generator) -> str:
    """Higher-merit applicants are more likely to give strong answers, but the
    mapping is noisy on purpose so the grader's job is non-trivial."""
    if merit_score >= 75:
        weights = [0.55, 0.15, 0.05, 0.25]
    elif merit_score >= 55:
        weights = [0.30, 0.30, 0.15, 0.25]
    else:
        weights = [0.10, 0.45, 0.30, 0.15]
    return str(rng.choice(TIERS, p=weights))


def generate_answer(question: str, time_seconds: int, tier: str,
                    rng: np.random.Generator) -> str:
    """Write one answer transcript in the style of the given tier."""
    target = _target_words(time_seconds, rng)
    return _compose(_POOLS[tier], target, rng)


def generate_for_applicant(
    merit_score: float,
    questions: list[tuple[int, str, int]],
    *,
    seed: int,
) -> list[tuple[AnswerLabel, str]]:
    """Produce (label, transcript_text) for each (index, question, time)."""
    rng = np.random.default_rng(seed)
    out: list[tuple[AnswerLabel, str]] = []
    for idx, question, time_s in questions:
        tier = _pick_tier(merit_score, rng)
        text = generate_answer(question, time_s, tier, rng)
        low, high = TIER_SCORE_BAND[tier]
        label = AnswerLabel(
            question_index=idx,
            question=question,
            tier=tier,
            expected_score_low=low,
            expected_score_high=high,
            is_ai_scripted=(tier == "ai_scripted"),
            word_count=len(text.split()),
        )
        out.append((label, text))
    return out
