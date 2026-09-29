"""Generate synthetic vision-LLM frame descriptions per interview answer.

Mimics the free-text output of the "Get Video Frame Description by Ollama"
notebook (a Gemma-3 description of the middle interview frame). The text is
written to the same folder the notebook uses, so fusion treats our descriptions
and the real ones identically.

Each description describes the interview setting. Some settings are clean and
professional, others are distracting; fusion turns this into a simple
visual-distraction feature via the keywords below. The setting is mostly
independent of answer quality (a good candidate can sit in a messy room), with
only a slight lean, so the feature is realistically weak.
"""

from __future__ import annotations

import numpy as np

# Keywords fusion looks for to flag a distracting setting. Keep in sync with
# pipeline/fusion.py.
DISTRACTION_KEYWORDS = ("cluttered", "dim", "messy", "dark", "busy background",
                        "poorly lit", "noisy", "untidy")

_CLEAN = (
    "The candidate is seated in a well-lit, tidy room, centred in the frame and "
    "dressed in neat business attire against a plain, uncluttered background.",
    "A person sits facing the camera in a bright, professional setting; the "
    "background is clean and free of distractions, and the lighting is even.",
    "The frame shows a calm, well-organised home office with soft lighting and a "
    "plain wall behind the smartly dressed candidate.",
)
_DISTRACTING = (
    "The candidate sits in a dim, cluttered room with a busy background of shelves "
    "and posters; the lighting is poor and the framing is slightly off-centre.",
    "A person is visible in a dark, messy space with an untidy, noisy background "
    "and uneven, poorly lit conditions.",
    "The frame shows a cramped, cluttered room with a dim, busy background and the "
    "candidate partly in shadow.",
)


def generate_frame_description(tier: str, rng: np.random.Generator) -> str:
    """Return a scene description; stronger answers lean slightly more professional."""
    p_distract = 0.18 if tier == "strong" else 0.30
    pool = _DISTRACTING if rng.random() < p_distract else _CLEAN
    return str(rng.choice(pool))
