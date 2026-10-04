"""Layer 1: the tabular applicant records.

Each applicant gets academic features (GPA, test score, English score, work
experience), demographic attributes, and a "ground-truth" merit score plus an
admit decision. The merit score is built only from academic features, so the
fair, correct label never depends on the protected attribute.

To study fairness we add a tunable, *unfair* gap on purpose. We do NOT change
merit. Instead, one group's measured test score is nudged down by `bias_gap`,
imitating unequal access to test preparation. A naive model that leans on the
test score will then look unfair to that group, giving the mitigation step
something real to correct.
"""

from dataclasses import dataclass, asdict, field

import numpy as np

from .. import config
from .names import make_name


@dataclass
class Applicant:
    applicant_id: str
    name: str
    study_program: str          # canonical key, e.g. "Aerospace Engineering"
    study_program_raw: str      # original TSV label, may include emoji

    # Demographics (protected attributes for the fairness study).
    gender: str
    region: str
    age: int

    # Academic features. `test_score` is the *measured* value (carries the
    # injected gap); `test_score_true` is the underlying ability with no gap.
    gpa: float                  # 0-4 scale
    test_score: float           # 0-100
    test_score_true: float      # 0-100, before the unfair gap is applied
    english_score: float        # IELTS-like, 0-9
    work_experience_years: float

    # Ground truth, derived only from academic ability (no demographics).
    merit_score: float          # 0-100
    admit: bool

    # Per-question interview answer quality, filled in by the answers layer.
    answer_tiers: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        """Flat dict for CSV output (drops the nested answer_tiers)."""
        row = asdict(self)
        row.pop("answer_tiers", None)
        return row


def _round(x: float, n: int = 2) -> float:
    return float(np.round(x, n))


def generate_applicants(
    programs: list[tuple[str, str]],
    n: int,
    *,
    seed: int = 7,
    protected_attribute: str = config.DEFAULT_PROTECTED_ATTRIBUTE,
    disadvantaged_value: str = "region_d",
    bias_gap: float = 12.0,
    admit_rate: float = 0.45,
) -> list[Applicant]:
    """Create `n` synthetic applicants.

    programs: list of (canonical_key, raw_label) pairs to assign in round-robin.
    bias_gap: points subtracted from the measured test score of the
        disadvantaged group. Set to 0.0 to generate a perfectly fair cohort.
    admit_rate: roughly what fraction of applicants are admitted; sets the
        merit-score cutoff for the admit decision.
    """
    rng = np.random.default_rng(seed)
    applicants: list[Applicant] = []

    for i in range(n):
        program_key, program_raw = programs[i % len(programs)]
        region = str(rng.choice(config.REGIONS))
        gender = str(rng.choice(config.GENDERS))
        age = int(rng.integers(config.AGE_RANGE[0], config.AGE_RANGE[1] + 1))

        # Underlying ability, drawn independently of demographics.
        gpa = float(np.clip(rng.normal(3.0, 0.5), 0.0, 4.0))
        test_true = float(np.clip(rng.normal(70, 12), 0, 100))
        english = float(np.clip(rng.normal(6.8, 0.9), 0.0, 9.0))
        work_exp = float(np.clip(rng.exponential(1.5), 0.0, 12.0))

        # Apply the unfair gap to the *measured* test score only.
        test_measured = test_true
        if protected_attribute == "region" and region == disadvantaged_value:
            test_measured = float(np.clip(test_true - bias_gap, 0, 100))

        # Merit uses true ability, so the correct label stays fair.
        merit = (
            0.30 * (gpa / 4.0 * 100)
            + 0.35 * test_true
            + 0.20 * (english / 9.0 * 100)
            + 0.15 * min(work_exp, 6) / 6 * 100
        )
        merit = _round(float(np.clip(merit + rng.normal(0, 3), 0, 100)))

        applicants.append(
            Applicant(
                applicant_id=f"{i}_{i}",
                name=make_name(region, rng),
                study_program=program_key,
                study_program_raw=program_raw,
                gender=gender,
                region=region,
                age=age,
                gpa=_round(gpa),
                test_score=_round(test_measured),
                test_score_true=_round(test_true),
                english_score=_round(english, 1),
                work_experience_years=_round(work_exp, 1),
                merit_score=merit,
                admit=False,  # set below once we know the cohort cutoff
            )
        )

    # Admit the top `admit_rate` fraction by merit.
    cutoff = float(np.quantile([a.merit_score for a in applicants], 1 - admit_rate))
    for a in applicants:
        a.admit = a.merit_score >= cutoff

    return applicants
