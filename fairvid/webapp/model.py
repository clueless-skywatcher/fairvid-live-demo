"""Verdict + explanations for the live demo.

On startup it builds a small synthetic cohort, trains the interpretable scoring
model, and picks one borderline candidate to pre-load (their academic record and
diploma/transcript are already "in the system"). When you record an interview,
`score_live` fuses that pre-loaded academic profile with the live-extracted
interview, behaviour and frame features, returns the admission probability and
decision, and the SHAP / LIME / counterfactual explanations.
"""

import numpy as np

from .. import config
from ..datagen.generate import generate_cohort
from ..pipeline import explain, scoring
from ..pipeline.fusion import build_cohort

_S: dict = {}


# How much each feature should count toward the (demo) reference decision. Signs
# are deliberate: a better interview, calmer behaviour and a tidy setting help;
# reading from a script, fidgeting and a distracting room hurt. This blended
# label makes the model's coefficients sensible so the live interview visibly
# moves the verdict (the thesis cohort keeps an academics-only label).
_WEIGHTS = {
    "gpa": 0.18, "test_score": 0.14, "english_score": 0.10, "work_experience_years": 0.08,
    "interview_overall_mean": 0.16, "interview_relevance_mean": 0.10, "interview_ai_flag_rate": -0.10,
    "behaviour_composite": 0.08, "behaviour_reading_prob": -0.06, "behaviour_smile": 0.05,
    "visual_distraction": -0.03,
}


def _blended_label(cohort, admit_rate: float = 0.45):
    X, names = cohort.X, cohort.feature_names
    z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    score = sum(_WEIGHTS[n] * z[:, i] for i, n in enumerate(names) if n in _WEIGHTS)
    cutoff = float(np.quantile(score, 1 - admit_rate))
    return (score >= cutoff).astype(int)


def init() -> None:
    """Generate the cohort (once), train the scorer, choose the candidate."""
    paths = config.Paths()
    if not paths.application_root.is_dir():
        generate_cohort(n=80, questions_per_applicant=3, seed=7)
    cohort = build_cohort(paths)
    cohort.y = _blended_label(cohort)          # label depends on record + interview
    sm = scoring.train_scorer(cohort, seed=7)
    probs = sm.score(cohort.X)
    # a borderline candidate (prob nearest 0.5) so the interview actually swings it
    idx = int(np.argmin(np.abs(probs - 0.5)))
    _S.update(paths=paths, cohort=cohort, sm=sm, idx=idx,
              rec=cohort.records[idx], names=cohort.feature_names,
              global_shap=explain.global_importance(sm),
              metrics=scoring.evaluate(sm))


def candidate() -> dict:
    r = _S["rec"]
    return {
        "applicant_id": r["applicant_id"], "name": r.get("name", "Candidate"),
        "study_program": r.get("study_program", ""),
        "gpa": r["gpa"], "test_score": r["test_score"],
        "english_score": r["english_score"], "work_experience_years": r["work_experience_years"],
        "gender": r.get("gender", ""), "region": r.get("region", ""), "age": r.get("age", ""),
    }


def candidate_doc_dir():
    return _S["paths"].documents_dir(_S["rec"]["applicant_id"])


def candidate_documents() -> dict:
    """The fields READ from the candidate's diploma + marksheet (the reference).

    For the synthetic documents we read the ground-truth fields that were printed
    on them (in production this is the Tesseract OCR output). These feed the
    verdict alongside the recorded video interview.
    """
    import json
    p = _S["paths"].doc_groundtruth_dir(_S["rec"]["applicant_id"]) / "extracted_fields.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def model_info() -> dict:
    return {"metrics": _S["metrics"], "global_shap": _S["global_shap"],
            "n_cohort": int(len(_S["cohort"].y))}


def score_live(interview: dict, behaviour: dict, visual_distraction: float) -> dict:
    """Fuse the pre-loaded academic features with live features and decide."""
    r, sm, names = _S["rec"], _S["sm"], _S["names"]
    feat = {
        "gpa": r["gpa"], "test_score": r["test_score"],
        "english_score": r["english_score"], "work_experience_years": r["work_experience_years"],
        "interview_overall_mean": interview["overall"],
        "interview_relevance_mean": interview["relevance"],
        "interview_ai_flag_rate": interview["ai_rate"],
        "behaviour_composite": behaviour["composite"],
        "behaviour_reading_prob": behaviour["reading_prob"],
        "behaviour_smile": behaviour["smile"],
        "visual_distraction": visual_distraction,
    }
    x = np.array([feat[n] for n in names], dtype=float)
    prob = float(sm.score(x.reshape(1, -1))[0])
    return {
        "probability": round(prob, 3),
        "admit": bool(prob >= 0.5),
        "features": {k: round(v, 2) for k, v in feat.items()},
        "shap_local": explain.local_explanation(sm, x),
        "lime": explain.lime_explanation(sm, x)[:5],
        "counterfactual": explain.counterfactual(sm, x, target=1),
    }
