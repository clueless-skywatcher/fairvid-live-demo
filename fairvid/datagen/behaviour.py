"""Generate synthetic MediaPipe-style behaviour metrics per interview answer.

The output JSON uses the exact keys the "Multimodal Behaviour Analysis" notebook
writes (after its get_cleaned_metrics step), so fusion reads our synthetic files
and the real notebook files with the same code.

Values are correlated with the answer's quality tier so the behaviour signal is
meaningful — most importantly, an AI-scripted answer shows the hallmarks of
reading from a script: high reading probability, more gaze aversion and downward
gaze, and little smiling.
"""

from __future__ import annotations

import numpy as np

# tier -> (composite, reading_prob, gaze_aversion, smile_freq) sampling ranges
_PROFILE = {
    "strong":      dict(comp=(78, 95), read=(2, 22),  gaze=(0.05, 0.20), smile=(20, 55)),
    "weak":        dict(comp=(55, 78), read=(10, 35), gaze=(0.10, 0.30), smile=(5, 25)),
    "off_topic":   dict(comp=(50, 75), read=(10, 30), gaze=(0.25, 0.50), smile=(5, 20)),
    "ai_scripted": dict(comp=(60, 85), read=(55, 90), gaze=(0.20, 0.45), smile=(2, 15)),
}


def generate_behaviour(tier: str, rng: np.random.Generator) -> dict:
    """Return one behaviour-metrics dict in the notebook's JSON schema."""
    p = _PROFILE.get(tier, _PROFILE["weak"])
    composite = float(rng.uniform(*p["comp"]))
    reading = float(rng.uniform(*p["read"]))
    gaze = float(rng.uniform(*p["gaze"]))
    smile_freq = float(rng.uniform(*p["smile"]))

    # Movement is inversely tied to the composite score (stiller = higher score),
    # matching how the notebook derives the composite from movement.
    stillness = composite / 100.0
    mean_head_speed = float(rng.uniform(1.0, 12.0) * (1.1 - stillness))
    rapid = float(rng.uniform(0, 40) * (1.1 - stillness))
    swing = float(rng.uniform(0, 30) * (1.1 - stillness))
    body = float(rng.uniform(0.0, 0.05) * (1.1 - stillness))
    look_down = float(rng.uniform(0.3, 0.5)) if tier == "ai_scripted" else float(rng.uniform(-0.1, 0.2))
    blink = float(rng.uniform(6, 14)) if tier == "ai_scripted" else float(rng.uniform(10, 24))

    # Match get_cleaned_metrics rounding: 1 decimal, 3 for mean body movement.
    return {
        "Mean head speed": round(mean_head_speed, 1),
        "Rapid movement": round(rapid, 1),
        "Swing movement": round(swing, 1),
        "Mean body movement": round(body, 3),
        "Composite score": round(composite, 1),
        "Gaze Aversion": round(gaze, 1) if gaze >= 1 else round(gaze, 2),
        "Reading Prob": round(reading, 1),
        "Look Down Intensity": round(look_down, 2),
        "Blink Rate (BPM)": round(blink, 1),
        "Smile Frequency": round(smile_freq, 1),
        "Average Smile Intensity": round(smile_freq / 100.0 + rng.uniform(0, 0.1), 2),
        "Is Speaking": True,
        "Jaw Variance": round(float(rng.uniform(0.05, 0.2)), 3),
    }
