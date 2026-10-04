"""Prosody and optional speech-emotion features for one interview audio file.

This follows `extract_video_interviews_audio_emotion.ipynb`. Prosody (tempo,
silence, pitch) uses librosa when it is installed. Emotion labels use a
wav2vec2 classifier when ``transformers`` is installed. If either library is
missing, the matching fields are left empty and ``ok`` stays false for that
part, so the rest of the demo still runs.

Output keys match the notebook JSON:

- ``tempo_bpm``
- ``silence_ratio``
- ``pitch_avg_hz``
- ``pitch_std_hz``
- ``emotions`` — label to probability, top 5, first 30 seconds of audio
"""

import os
from pathlib import Path

_EMOTION_MODEL = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
_classifier = None


def _emotion_labels(samples, sample_rate: int) -> dict:
    """Top-5 emotion probabilities, or {} if the classifier cannot be loaded."""
    global _classifier
    try:
        from transformers import pipeline
    except ImportError:
        return {}
    if _classifier is None:
        _classifier = pipeline("audio-classification", model=_EMOTION_MODEL)
    chunk = samples[: 30 * sample_rate]
    try:
        labels = _classifier(chunk, top_k=5)
    except Exception:
        labels = _classifier({"array": chunk, "sampling_rate": sample_rate}, top_k=5)
    return {item["label"]: float(item["score"]) for item in labels}


def analyze_audio(file_path, *, emotions: bool | None = None) -> dict:
    """Return the notebook's emotion/prosody dict for one audio file."""
    path = Path(file_path)
    if emotions is None:
        emotions = os.environ.get("FAIRVID_AUDIO_EMOTION", "").lower() in ("1", "true", "yes")
    result = {
        "ok": False,
        "backend": "unavailable",
        "source": path.name,
        "tempo_bpm": None,
        "silence_ratio": None,
        "pitch_avg_hz": None,
        "pitch_std_hz": None,
        "emotions": {},
    }
    try:
        import librosa
        import numpy as np
    except ImportError:
        result["error"] = "librosa is not installed; prosody agent skipped"
        return result

    y, sr = librosa.load(str(path), sr=16000)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
    result["tempo_bpm"] = float(tempo[0])

    non_silent = librosa.effects.split(y, top_db=20)
    voiced = sum(end - start for start, end in non_silent) / sr
    total = float(librosa.get_duration(y=y, sr=sr)) or 1.0
    result["silence_ratio"] = float((total - voiced) / total)

    f0, _voiced_flag, _voiced_probs = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"))
    valid = f0[~np.isnan(f0)]
    if len(valid):
        result["pitch_avg_hz"] = float(np.mean(valid))
        result["pitch_std_hz"] = float(np.std(valid))

    if emotions:
        try:
            result["emotions"] = _emotion_labels(y, sr)
        except Exception as exc:
            result["emotion_error"] = f"{type(exc).__name__}: {exc}"

    result["ok"] = True
    result["backend"] = "librosa"
    if result["emotions"]:
        result["backend"] = "librosa+wav2vec2"
    return result
