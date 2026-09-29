"""Fusion: combine each applicant's modalities into one feature row.

This is "late fusion" in the sense of the Hangloo & Arora review cited in the
thesis: each modality is summarised on its own, then the summaries are joined
into a single feature vector for the scoring model.

Modalities combined here:
  - structured record : GPA, measured test score, English score, work experience
  - interview         : aggregated grades from the grader stage
  - (document text is available via the OCR ground truth but, for the initial
     study, the GPA it carries already appears in the structured record, so we
     keep the feature set small and interpretable)

Returns a `Cohort` holding the feature matrix X, feature names, the admit label
y, and the protected-attribute column, ready for scoring and fairness work.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config
from .grader import grade_transcript

# Keywords that mark a distracting interview setting in a frame description.
# Kept in sync with datagen/frames.py so real and synthetic descriptions agree.
_DISTRACTION_KEYWORDS = ("cluttered", "dim", "messy", "dark", "busy background",
                         "poorly lit", "noisy", "untidy")

# The feature columns fed to the scoring model, in order. The last four come from
# the perceptual stages (MediaPipe behaviour + vision-LLM frame description),
# read from the same folders the Colab notebooks write to.
FEATURE_NAMES = [
    "gpa",
    "test_score",
    "english_score",
    "work_experience_years",
    "interview_overall_mean",
    "interview_relevance_mean",
    "interview_ai_flag_rate",
    "behaviour_composite",
    "behaviour_reading_prob",
    "behaviour_smile",
    "visual_distraction",
]


@dataclass
class Cohort:
    X: np.ndarray                # (n_applicants, n_features)
    y: np.ndarray                # (n_applicants,) admit label, 0/1
    feature_names: list[str]
    protected: np.ndarray        # (n_applicants,) protected-attribute values
    protected_name: str
    ids: list[str]
    records: list[dict]          # full ground-truth record per applicant


def _aggregate_interview(applicant_dir: Path, study_program_raw: str) -> dict:
    """Grade every transcript for one applicant and average the results."""
    tr_dir = (applicant_dir / config.TRANSCRIPTS_DIR
              / config.slugify(study_program_raw))
    overalls, relevances, ai_flags = [], [], []
    if tr_dir.is_dir():
        for txt in sorted(tr_dir.glob("*.txt")):
            transcript = txt.read_text(encoding="utf-8")
            # Recover the question text from the filename slug is lossy, so we
            # pass the slug; the grader does not rely on the question wording.
            g = grade_transcript(txt.stem, transcript)
            overalls.append(g["overall_score"])
            relevances.append(g["metrics"]["relevance_score"])
            ai_flags.append(1.0 if g["ai_script_detection"]["is_likely_reading_llm_text"] else 0.0)
    if not overalls:
        return {"overall": 0.0, "relevance": 0.0, "ai_rate": 0.0}
    return {
        "overall": float(np.mean(overalls)),
        "relevance": float(np.mean(relevances)),
        "ai_rate": float(np.mean(ai_flags)),
    }


def _aggregate_behaviour(applicant_dir: Path) -> dict:
    """Average the MediaPipe behaviour metrics over an applicant's answers.

    Reads every JSON under the behaviour folder (recursively, so it works for
    both our synthetic layout and the notebook's program-subfolder layout). If
    no behaviour files exist (e.g. a real applicant without this stage), returns
    neutral midpoints so the feature is defined.
    """
    comp, read, smile = [], [], []
    beh_dir = applicant_dir / config.BLENDSHAPE_DIR
    if beh_dir.is_dir():
        for j in beh_dir.rglob("*.json"):
            try:
                d = json.loads(j.read_text(encoding="utf-8"))
            except Exception:
                continue
            comp.append(float(d.get("Composite score", 70.0)))
            read.append(float(d.get("Reading Prob", 20.0)))
            smile.append(float(d.get("Smile Frequency", 20.0)))
    if not comp:
        return {"composite": 70.0, "reading_prob": 20.0, "smile": 20.0}
    return {"composite": float(np.mean(comp)),
            "reading_prob": float(np.mean(read)),
            "smile": float(np.mean(smile))}


def _aggregate_frames(applicant_dir: Path) -> float:
    """Fraction of an applicant's frame descriptions that mention a distracting
    setting. Reads every video_frame_text_* folder (any model). 0.0 if none."""
    texts = []
    for ft_dir in applicant_dir.glob("video_frame_text_*"):
        for txt in ft_dir.rglob("*.txt"):
            texts.append(txt.read_text(encoding="utf-8").lower())
    if not texts:
        return 0.0
    flagged = sum(any(k in t for k in _DISTRACTION_KEYWORDS) for t in texts)
    return flagged / len(texts)


def build_cohort(paths: config.Paths | None = None,
                 protected_name: str = config.DEFAULT_PROTECTED_ATTRIBUTE) -> Cohort:
    """Load every applicant under the cohort root and fuse their modalities."""
    paths = paths or config.Paths()
    app_root = paths.application_root
    if not app_root.is_dir():
        raise FileNotFoundError(
            f"No cohort found at {app_root}. Run `python -m fairvid.datagen` first."
        )

    rows, labels, protected, ids, records = [], [], [], [], []
    for applicant_dir in sorted(app_root.iterdir()):
        rec_path = applicant_dir / config.GROUND_TRUTH_DIR / "record.json"
        if not rec_path.exists():
            continue
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        interview = _aggregate_interview(applicant_dir, rec["study_program_raw"])
        behaviour = _aggregate_behaviour(applicant_dir)
        visual_distraction = _aggregate_frames(applicant_dir)

        rows.append([
            rec["gpa"],
            rec["test_score"],
            rec["english_score"],
            rec["work_experience_years"],
            interview["overall"],
            interview["relevance"],
            interview["ai_rate"],
            behaviour["composite"],
            behaviour["reading_prob"],
            behaviour["smile"],
            visual_distraction,
        ])
        labels.append(1 if rec["admit"] else 0)
        protected.append(rec[protected_name])
        ids.append(rec["applicant_id"])
        records.append(rec)

    return Cohort(
        X=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=int),
        feature_names=list(FEATURE_NAMES),
        protected=np.asarray(protected),
        protected_name=protected_name,
        ids=ids,
        records=records,
    )
