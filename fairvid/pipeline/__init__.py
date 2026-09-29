"""The core evaluation stages that turn per-applicant artifacts into a score.

Flow:  grader -> fusion -> scoring -> explain / fairness

  grader   - reads each interview transcript and produces a grade JSON
             (same shape as the Gemini "transcript auditor" notebook output)
  fusion   - combines the structured record, the interview grades, and the
             document text into one feature row per applicant
  scoring  - trains an interpretable model that predicts the admit decision
  explain  - SHAP, LIME, and counterfactual explanations of that model
  fairness - measures group disparities and applies mitigation

Everything runs offline. In Colab you can replace `grader` with the real
Gemini grading stage; nothing downstream changes.
"""
