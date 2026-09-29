"""Explainability: SHAP, LIME, and counterfactuals for the scoring model.

These three methods map directly onto the explainable-AI papers in the thesis:
  - SHAP            (Rico-Juan et al.; Johora et al.)  - feature attributions
  - LIME            (Johora et al.)                    - local linear surrogate
  - counterfactual  (Afzaal et al., the DICE approach) - "what would flip this?"

SHAP uses the `shap` library when installed; otherwise it falls back to exact
Shapley values, which are cheap to compute in closed form for our linear model.
"""

from __future__ import annotations

import numpy as np

from .scoring import ScoreModel


# --- SHAP --------------------------------------------------------------------

def shap_values(sm: ScoreModel, X_raw: np.ndarray) -> np.ndarray:
    """Return SHAP values (n_samples, n_features) in standardised-feature space.

    For a logistic-regression model the log-odds are linear, so the exact
    Shapley value of feature i for sample x is simply
        coef_i * (x_i - mean_i)
    which is what `shap.LinearExplainer` computes too. We try the library first
    so the output matches what a reader would reproduce with `shap`, then fall
    back to the closed form.
    """
    Xs = sm.scaler.transform(X_raw)
    try:
        import shap
        explainer = shap.LinearExplainer(sm.model, sm.scaler.transform(sm.X_train))
        vals = explainer.shap_values(Xs)
        return np.asarray(vals)
    except Exception:
        coef = sm.model.coef_[0]
        mean = sm.scaler.transform(sm.X_train).mean(axis=0)
        return (Xs - mean) * coef


def global_importance(sm: ScoreModel) -> list[tuple[str, float]]:
    """Mean absolute SHAP value per feature, sorted high to low."""
    vals = np.abs(shap_values(sm, sm.X_train)).mean(axis=0)
    pairs = list(zip(sm.feature_names, (round(float(v), 4) for v in vals)))
    return sorted(pairs, key=lambda p: p[1], reverse=True)


def local_explanation(sm: ScoreModel, x_raw: np.ndarray) -> list[tuple[str, float]]:
    """Per-feature SHAP contribution for a single applicant (signed)."""
    vals = shap_values(sm, x_raw.reshape(1, -1))[0]
    pairs = list(zip(sm.feature_names, (round(float(v), 4) for v in vals)))
    return sorted(pairs, key=lambda p: abs(p[1]), reverse=True)


# --- LIME --------------------------------------------------------------------

def lime_explanation(sm: ScoreModel, x_raw: np.ndarray, *,
                     n_samples: int = 500, seed: int = 0) -> list[tuple[str, float]]:
    """Fit a local linear surrogate around one applicant and return its weights.

    We jitter the standardised features, ask the real model for probabilities,
    weight nearby points more, and fit a small weighted linear regression. The
    surrogate's coefficients are the LIME explanation.
    """
    rng = np.random.default_rng(seed)
    xs = sm.scaler.transform(x_raw.reshape(1, -1))[0]
    noise = rng.normal(0, 1.0, size=(n_samples, len(xs)))
    samples = xs + noise
    proba = sm.model.predict_proba(samples)[:, 1]

    # Weight by closeness to the point of interest (RBF kernel).
    dist = np.linalg.norm(samples - xs, axis=1)
    weights = np.exp(-(dist ** 2) / (2 * (0.75 ** 2)))

    # Weighted least squares with an intercept.
    A = np.hstack([samples, np.ones((n_samples, 1))])
    W = np.diag(weights)
    coef = np.linalg.lstsq(A.T @ W @ A, A.T @ W @ proba, rcond=None)[0][:-1]
    pairs = list(zip(sm.feature_names, (round(float(c), 4) for c in coef)))
    return sorted(pairs, key=lambda p: abs(p[1]), reverse=True)


# --- Counterfactual (DICE-style) --------------------------------------------

def counterfactual(sm: ScoreModel, x_raw: np.ndarray, *,
                   target: int = 1, threshold: float = 0.5,
                   step: float = 0.02, max_iter: int = 2000) -> dict:
    """Find a small, realistic change that flips the decision to `target`.

    We nudge the features along the model's gradient (in standardised space)
    until the prediction crosses the threshold, then report the change needed in
    the original units. This is the single-counterfactual core of the DICE idea
    (Afzaal et al.); generating a diverse set is left as future work.
    """
    coef = sm.model.coef_[0]
    direction = coef if target == 1 else -coef
    xs = sm.scaler.transform(x_raw.reshape(1, -1))[0].copy()

    start_p = float(sm.model.predict_proba(xs.reshape(1, -1))[0, 1])
    reached = (start_p >= threshold) == bool(target)
    it = 0
    unit = direction / (np.linalg.norm(direction) + 1e-9)
    while not reached and it < max_iter:
        xs = xs + step * unit
        p = float(sm.model.predict_proba(xs.reshape(1, -1))[0, 1])
        reached = (p >= threshold) == bool(target)
        it += 1

    x_new_raw = sm.scaler.inverse_transform(xs.reshape(1, -1))[0]
    deltas = {
        name: round(float(x_new_raw[i] - x_raw[i]), 3)
        for i, name in enumerate(sm.feature_names)
        if abs(x_new_raw[i] - x_raw[i]) > 1e-3
    }
    return {
        "start_probability": round(start_p, 3),
        "final_probability": round(float(sm.model.predict_proba(xs.reshape(1, -1))[0, 1]), 3),
        "reached_target": bool(reached),
        "iterations": it,
        "changes_in_original_units": deltas,
    }
