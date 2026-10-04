"""Turn the joined stage payloads into a decision and a list of improvements.

This does not retrain the web-demo model. It uses the same feature list and the
same signs as the demo weights, so a higher interview score helps and a high
reading-from-notes score hurts. The letter then names the mutable features that
are still on the weak side of a plain target.
"""

import math

from ..pipeline.fusion import FEATURE_SPECS

# Signs match fairvid.webapp.model._WEIGHTS.
_WEIGHTS = {
    "gpa": 0.18,
    "test_score": 0.14,
    "english_score": 0.10,
    "work_experience_years": 0.08,
    "interview_overall_mean": 0.16,
    "interview_relevance_mean": 0.10,
    "interview_ai_flag_rate": -0.10,
    "behaviour_composite": 0.08,
    "behaviour_reading_prob": -0.06,
    "behaviour_smile": 0.05,
    "visual_distraction": -0.03,
}

# A value on the good side of this target does not generate advice.
_TARGETS = {
    "gpa": 3.2,
    "test_score": 75.0,
    "english_score": 6.5,
    "work_experience_years": 1.0,
    "interview_overall_mean": 75.0,
    "interview_relevance_mean": 7.0,
    "interview_ai_flag_rate": 0.2,
    "behaviour_composite": 75.0,
    "behaviour_reading_prob": 30.0,
    "behaviour_smile": 25.0,
    "visual_distraction": 0.2,
}

_ADVICE = {
    "interview_overall_mean":
        "Give a fuller answer: one concrete example, what you did, and what changed.",
    "interview_relevance_mean":
        "Answer the question directly in the first sentences, then add the example.",
    "interview_ai_flag_rate":
        "Speak in your own words. A polished script read aloud is flagged.",
    "behaviour_composite":
        "Sit still and keep your head steady while you speak.",
    "behaviour_reading_prob":
        "Look at the camera instead of down at notes.",
    "behaviour_smile":
        "Let your expression move naturally. A fixed face reads as flat.",
    "visual_distraction":
        "Record in a tidy, well-lit room with a plain background.",
}

_RECORD_NOTES = {
    "gpa": "GPA is already on your record. This flow does not change it.",
    "test_score": "The test score is already on your record.",
    "english_score": "The English score is already on your record.",
    "work_experience_years": "Work experience is already on your record.",
}

_DEFAULTS = {
    "gpa": 3.0,
    "test_score": 70.0,
    "english_score": 6.0,
    "work_experience_years": 0.0,
    "interview_overall_mean": 60.0,
    "interview_relevance_mean": 6.0,
    "interview_ai_flag_rate": 0.0,
    "behaviour_composite": 70.0,
    "behaviour_reading_prob": 20.0,
    "behaviour_smile": 20.0,
    "visual_distraction": 0.0,
}


def features_from_payload(payload: dict) -> dict[str, float]:
    features = dict(_DEFAULTS)
    for name in features:
        if name in payload and payload[name] is not None:
            features[name] = float(payload[name])
    return features


def decide(features: dict[str, float]) -> dict:
    """Map features to a probability in 0..1 and an admit flag at 0.5."""
    specs = {spec.name: spec for spec in FEATURE_SPECS}
    logit = 0.0
    for name, weight in _WEIGHTS.items():
        spec = specs[name]
        span = spec.high - spec.low or 1.0
        midpoint = (spec.high + spec.low) / 2.0
        logit += weight * ((features[name] - midpoint) / (span / 2.0))
    probability = 1.0 / (1.0 + math.exp(-3.0 * logit))
    return {
        "probability": round(probability, 3),
        "admit": probability >= 0.5,
        "features": {name: round(value, 2) for name, value in features.items()},
    }


def improvements(features: dict[str, float]) -> tuple[list[str], list[str]]:
    """Actionable interview advice, then notes about the fixed academic record."""
    advice = []
    notes = []
    for name, target in _TARGETS.items():
        value = features[name]
        weight = _WEIGHTS[name]
        weak = value < target if weight > 0 else value > target
        if not weak:
            continue
        if name in _ADVICE:
            advice.append(_ADVICE[name])
        elif name in _RECORD_NOTES:
            notes.append(_RECORD_NOTES[name])
    return advice, notes
