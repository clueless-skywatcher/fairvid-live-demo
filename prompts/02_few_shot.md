# Prompt 2 - Few-shot applicant scoring

**Technique:** few-shot. Prompt 1 is extended with 3 known (X, y) pairs from Lab 1.2
([`data/feature-label-examples-thesis.md`](../data/feature-label-examples-thesis.md),
section 2B). The examples show the model the expected reasoning style, calibration,
and output format before it scores the new applicant.

The 3 examples cover different cases:

| Example | Case | y |
| :--- | :--- | :--- |
| 1 | Strong academic record and interview | admit, 0.94 |
| 2 | Clear but off-topic interview, flagged as AI-scripted | reject |
| 3 | Low GPA and test score, honest interview | reject, 0.03 |

The Lab 1.2 table does not give an eye-contact ratio for examples 2 and 3, so
`eye_contact_ratio` is `null` there. The table also gives no probability for
example 2. The value 0.12 below was added for this prompt. Examples 2 and 3 also
show the model how to handle a missing value in the data-understanding stage.

## SYSTEM

Same as [Prompt 1](01_zero_shot.md#system).

## USER

```text
Here are 3 applicants that were already scored. Use them as a reference for
reasoning, calibration and output format.

Example 1
X: {"study_program": "Computer Science", "gpa": 3.85, "test_score": 88, "english_score": 8.0, "work_experience_years": 3, "interview_mean_grade": 4.75, "interview_relevance": 4.8, "interview_clarity": 4.6, "ai_script_flag": 0, "eye_contact_ratio": 0.85}
y: {"understanding": "Strong applicant: GPA 3.85, test 88, IELTS 8.0, 3 years of experience, excellent interview (4.75/5). No data issues.", "reasoning": "The academic record is well above the typical range. English is strong. The interview is relevant and natural, with no script flag. Every major signal is positive.", "decision": "admit", "probability": 0.94, "top_factors": ["gpa: positive - 3.85 is near the top of the range", "interview_mean_grade: positive - 4.75/5 with high relevance", "test_score: positive - 88/100"], "what_would_change": "Only a large drop in the academic record (GPA below about 2.8) together with a weak interview would flip the decision."}

Example 2
X: {"study_program": "Computer Science", "gpa": 3.20, "test_score": 72, "english_score": 6.5, "work_experience_years": 0, "interview_mean_grade": 2.10, "interview_relevance": 2.0, "interview_clarity": 4.9, "ai_script_flag": 1, "eye_contact_ratio": null}
y: {"understanding": "Average academic record (GPA 3.20, test 72), IELTS 6.5, no experience. The interview is very clear (4.9) but off-topic (relevance 2.0) and flagged as AI-scripted. eye_contact_ratio is missing.", "reasoning": "The academic record alone is borderline. High clarity with low relevance, plus the script flag, suggests a read or generated answer, so the interview gives no reliable positive evidence. The missing eye-contact value is ignored, since it is a weak signal.", "decision": "reject", "probability": 0.12, "top_factors": ["ai_script_flag: negative - answers look AI-written", "interview_relevance: negative - 2.0/5, answers off-topic", "work_experience_years: negative - none"], "what_would_change": "A genuine, relevant interview (grade 3.5 or higher, no script flag) would make this a borderline admit."}

Example 3
X: {"study_program": "Computer Science", "gpa": 2.40, "test_score": 65, "english_score": 6.0, "work_experience_years": 1, "interview_mean_grade": 3.20, "interview_relevance": 3.0, "interview_clarity": 3.5, "ai_script_flag": 0, "eye_contact_ratio": null}
y: {"understanding": "Low GPA (2.40), below-average test score (65), IELTS 6.0, 1 year of experience, average interview (3.2/5). eye_contact_ratio is missing.", "reasoning": "The academic record is well below the admitted range and English is under the 6.5 threshold. The interview is honest but only average, so it cannot compensate. The missing eye-contact value does not change the outcome.", "decision": "reject", "probability": 0.03, "top_factors": ["gpa: negative - 2.40 is well below the typical range", "test_score: negative - 65/100", "english_score: negative - 6.0 is below 6.5"], "what_would_change": "Raising the GPA by about 0.7 (to 3.1) and the test score by about 8 points (to 73) would flip the decision to admit."}

Now score this applicant. Return ONLY the JSON object for y.

Applicant X:
{applicant_json}
```

## Example input X

The same new applicant as in Prompt 1, so the two outputs can be compared:

```json
{
  "study_program": "Computer Science",
  "gpa": 3.10,
  "test_score": 71,
  "english_score": 6.5,
  "work_experience_years": 1.5,
  "interview_mean_grade": 3.8,
  "interview_relevance": 3.9,
  "interview_clarity": 3.6,
  "ai_script_flag": 0,
  "eye_contact_ratio": 0.72
}
```

## What to compare with Prompt 1

- **Calibration:** is the probability closer to the scale of the examples
  (0.94 for strong, 0.03 for weak)?
- **Format:** are `top_factors` written in the same `feature: direction - why` form?
- **Counterfactual:** is `what_would_change` concrete, with numbers, like in
  example 3?
