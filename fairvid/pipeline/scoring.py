"""Scoring: train an interpretable model to predict the admit decision.

We use logistic regression on standardised features, matching the transparent,
inspectable models in the Raftopoulos et al. admission-prediction paper cited in
the thesis. The model outputs both a probability (the "applicant score") and a
yes/no admit decision.

`train_scorer` returns a small bundle holding the fitted model, the scaler, and
the train/test split, so the explain and fairness stages can reuse exactly the
same fitted objects.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .fusion import Cohort


@dataclass
class ScoreModel:
    model: LogisticRegression
    scaler: StandardScaler
    feature_names: list[str]
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    idx_train: np.ndarray
    idx_test: np.ndarray

    def score(self, X_raw: np.ndarray) -> np.ndarray:
        """Return admit probabilities for raw (unscaled) feature rows."""
        return self.model.predict_proba(self.scaler.transform(X_raw))[:, 1]

    def decide(self, X_raw: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return (self.score(X_raw) >= threshold).astype(int)


def train_scorer(cohort: Cohort, *, test_size: float = 0.35,
                 seed: int = 7, drop_features: list[str] | None = None) -> ScoreModel:
    """Fit the scoring model.

    drop_features: feature names to exclude from training. Used by the fairness
        stage to retrain without a biased proxy (e.g. drop "test_score").
    """
    keep = [i for i, n in enumerate(cohort.feature_names)
            if not (drop_features and n in drop_features)]
    feat_names = [cohort.feature_names[i] for i in keep]
    X = cohort.X[:, keep]

    idx = np.arange(len(cohort.y))
    X_tr, X_te, y_tr, y_te, i_tr, i_te = train_test_split(
        X, cohort.y, idx, test_size=test_size, random_state=seed,
        stratify=cohort.y if cohort.y.sum() not in (0, len(cohort.y)) else None,
    )

    scaler = StandardScaler().fit(X_tr)
    model = LogisticRegression(max_iter=1000, random_state=seed)
    model.fit(scaler.transform(X_tr), y_tr)

    return ScoreModel(
        model=model, scaler=scaler, feature_names=feat_names,
        X_train=X_tr, X_test=X_te, y_train=y_tr, y_test=y_te,
        idx_train=i_tr, idx_test=i_te,
    )


def evaluate(sm: ScoreModel) -> dict:
    """Conformance of the model's decisions with the ground-truth admit label."""
    proba = sm.model.predict_proba(sm.scaler.transform(sm.X_test))[:, 1]
    pred = (proba >= 0.5).astype(int)
    out = {
        "n_test": int(len(sm.y_test)),
        "accuracy": round(float(accuracy_score(sm.y_test, pred)), 3),
        "f1": round(float(f1_score(sm.y_test, pred, zero_division=0)), 3),
    }
    # AUC needs both classes present in the test split.
    if len(set(sm.y_test)) == 2:
        out["roc_auc"] = round(float(roc_auc_score(sm.y_test, proba)), 3)
    return out
