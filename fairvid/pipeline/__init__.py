"""Agents that turn one applicant folder into a score.

The Colab notebooks run these stages one file at a time. Here the same jobs
are importable functions. Two tracks run side by side, then meet at fusion:

Document track
  pages        - glue page-level OCR / vision text into one file per document
  reconcile    - vote when several models summarised the same document
  eligibility  - fill the knowledge-base eligibility prompt (no cloud call)

Interview track
  audio_affect - tempo, pauses, and pitch from the extracted audio
  behaviour    - MediaPipe face metrics (reading, smile, head motion)
  vlm          - Gemma frame description, with an offline fallback
  grader       - transcript scores in the Gemini auditor JSON shape

Decision
  fusion       - one feature row per applicant
  scoring      - logistic regression admit probability
  explain      - SHAP, LIME, and a bounded counterfactual

The live web app calls the interview track on a recording. The document track
is already on disk for the pre-loaded candidate.
"""
