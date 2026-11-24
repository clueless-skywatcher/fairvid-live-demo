# FAIR-VID prompts (Lab 1.4)

This directory holds the prompts for the FAIR-VID admissions agent. FAIR-VID is the
thesis system *Applicant Scoring Model with Explanations and Fairness Verification*,
seen as one end-to-end AI agent.

## The agent as an end-to-end solution

```
X (applicant record + interview results)
  -> 1. Data understanding   check the features, flag missing or out-of-range values
  -> 2. Reasoning            weigh academic record, test, English, experience, interview
  -> 3. Inference            admit / reject + probability of admission
  -> 4. Output generation    JSON verdict + top factors + counterfactual advice
y (decision, probability, explanation)
```

### Input X

One applicant, as a JSON object:

| Field | Type | Range | Source in the pipeline |
| :--- | :--- | :--- | :--- |
| `study_program` | string | - | application form |
| `gpa` | float | 0.0-4.0 | transcript (OCR + reconciliation) |
| `test_score` | float | 0-100 | standardized test certificate |
| `english_score` | float | 0.0-9.0 (IELTS band) | language certificate |
| `work_experience_years` | float | >= 0 | CV |
| `interview_mean_grade` | float | 0.0-5.0 | Whisper transcript, graded by the LLM (ASAG) |
| `interview_relevance` | float | 0.0-5.0 | LLM grader sub-score |
| `interview_clarity` | float | 0.0-5.0 | LLM grader sub-score |
| `ai_script_flag` | int | 0 or 1 | LLM grader: answer looks read or AI-written |
| `eye_contact_ratio` | float | 0.0-1.0 | MediaPipe behaviour metrics |

Protected attributes (`gender`, `region`, `age`, `name`) can be in the raw record.
The agent must not use them. The fairness verification stage checks this
separately (demographic parity, equal opportunity).

### Output y

```json
{
  "understanding": "short restatement of the applicant and any data issues",
  "reasoning": "step-by-step weighing of the evidence",
  "decision": "admit | reject",
  "probability": 0.0,
  "top_factors": ["feature: direction and why"],
  "what_would_change": "smallest realistic change that would flip the decision"
}
```

## Files

| File | Technique | Description |
| :--- | :--- | :--- |
| [`01_zero_shot.md`](01_zero_shot.md) | Zero-shot | System instructions + one new applicant X. The model predicts y with no examples. |
| [`02_few_shot.md`](02_few_shot.md) | Few-shot | Same instructions + 3 known (X, y) pairs from [`data/feature-label-examples-thesis.md`](../data/feature-label-examples-thesis.md), then the new X. |

## Template convention

Each prompt file has a `SYSTEM` block and a `USER` block inside fenced code blocks.
The placeholder `{applicant_json}` is replaced with the JSON of the applicant to
score. The notebooks (Lab 1.5 / 1.6) load these files and fill the placeholder.
For Lab 1.6 (RAG), the fixed examples of the few-shot prompt are replaced by the 3
most similar examples retrieved from ChromaDB.

## Design choices

- **Fixed stages in the prompt.** The model must fill `understanding` and
  `reasoning` before `decision`. Each stage of the pipeline is then visible
  in the output.
- **JSON-only output.** The result can be parsed and fed to the fusion and
  explanation stages, and compared across prompts.
- **Explicit fairness rule.** Protected attributes are named and excluded, so the
  model cannot infer that they are allowed.
- **Counterfactual field.** Mirrors the DiCE explanation in the thesis: a rejected
  applicant learns what would change the outcome.
