"""Builds a complete synthetic cohort and writes it to disk.

What it produces, per applicant, under
  synthetic_data/dream_applicant_application/{applicant_id}/ :

  documents_image/                      diploma.png, transcript.png
  documents_image_groundtruth/          extracted_fields.json (correct OCR text)
  video_interviews_audio_transcriptions_text/{program}/{i}_{slug}.txt
                                        interview answer transcripts
  ground_truth/record.json              the applicant's full record
  ground_truth/answer_labels.json       quality tier + expected score per answer

And, for the whole cohort, under synthetic_data/ :
  applicants.csv                        one flat row per applicant
  cohort_manifest.json                  run settings + summary counts
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict

import numpy as np

from .. import config
from . import answers as answers_mod
from . import behaviour as behaviour_mod
from . import documents as documents_mod
from . import frames as frames_mod
from . import records as records_mod
from .questions import load_questions


def _assign_questions(program_questions, n_per_applicant, rng):
    """Pick up to `n_per_applicant` questions for a program."""
    if n_per_applicant >= len(program_questions):
        return list(program_questions)
    idxs = rng.choice(len(program_questions), size=n_per_applicant, replace=False)
    return [program_questions[i] for i in sorted(idxs)]


def generate_cohort(
    n: int = 24,
    *,
    questions_per_applicant: int = 4,
    seed: int = 7,
    bias_gap: float = 12.0,
    paths: config.Paths | None = None,
) -> dict:
    """Generate `n` applicants with documents, transcripts, and labels.

    Returns the cohort manifest (also written to disk).
    """
    paths = paths or config.Paths()
    rng = np.random.default_rng(seed)

    questions_by_program = load_questions()
    # Pair each canonical program key with one raw TSV label that maps to it.
    program_pairs: list[tuple[str, str]] = []
    for raw_label in questions_by_program:
        key = config.normalize_program(raw_label)
        if key in config.PROGRAM_SUBJECTS:
            program_pairs.append((key, raw_label))
    if not program_pairs:
        raise RuntimeError("No study programs matched PROGRAM_SUBJECTS.")

    applicants = records_mod.generate_applicants(
        program_pairs, n, seed=seed, bias_gap=bias_gap
    )

    paths.base_dir.mkdir(parents=True, exist_ok=True)
    csv_rows = []

    for ai, applicant in enumerate(applicants):
        a_seed = seed * 1000 + ai  # distinct, deterministic seed per applicant
        a_rng = np.random.default_rng(a_seed)

        # --- documents ---
        doc_fields = documents_mod.render_documents(applicant, paths, a_rng)
        gt_doc_dir = paths.doc_groundtruth_dir(applicant.applicant_id)
        gt_doc_dir.mkdir(parents=True, exist_ok=True)
        (gt_doc_dir / "extracted_fields.json").write_text(
            json.dumps(doc_fields, indent=2), encoding="utf-8"
        )

        # --- interview answers ---
        raw_label = applicant.study_program_raw
        all_q = questions_by_program[raw_label]
        chosen_q = _assign_questions(all_q, questions_per_applicant, a_rng)
        labelled = answers_mod.generate_for_applicant(
            applicant.merit_score, chosen_q, seed=a_seed
        )

        tr_dir = paths.transcripts_dir(applicant.applicant_id, raw_label)
        beh_dir = paths.blendshape_dir(applicant.applicant_id, raw_label)
        frame_dir = paths.frame_text_dir(applicant.applicant_id, raw_label)
        for d in (tr_dir, beh_dir, frame_dir):
            d.mkdir(parents=True, exist_ok=True)
        answer_labels = []
        for label, text in labelled:
            slug = config.slugify(label.question)[:50]
            stem = f"{label.question_index}_{slug}"
            (tr_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
            # MediaPipe-style behaviour JSON (same schema/folder as the notebook)
            (beh_dir / f"{stem}.json").write_text(
                json.dumps(behaviour_mod.generate_behaviour(label.tier, a_rng), indent=2),
                encoding="utf-8")
            # vision-LLM frame description (same folder as the Ollama/Gemma notebook)
            (frame_dir / f"{stem}.txt").write_text(
                frames_mod.generate_frame_description(label.tier, a_rng), encoding="utf-8")
            applicant.answer_tiers[str(label.question_index)] = label.tier
            answer_labels.append({**asdict(label), "transcript_file": f"{stem}.txt"})

        # --- ground truth ---
        gt_dir = paths.ground_truth_dir(applicant.applicant_id)
        gt_dir.mkdir(parents=True, exist_ok=True)
        (gt_dir / "record.json").write_text(
            json.dumps(asdict(applicant), indent=2), encoding="utf-8"
        )
        (gt_dir / "answer_labels.json").write_text(
            json.dumps(answer_labels, indent=2), encoding="utf-8"
        )

        csv_rows.append(applicant.to_row())

    # --- cohort-level outputs ---
    csv_path = paths.base_dir / "applicants.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    manifest = {
        "n_applicants": len(applicants),
        "questions_per_applicant": questions_per_applicant,
        "seed": seed,
        "bias_gap": bias_gap,
        "protected_attribute": config.DEFAULT_PROTECTED_ATTRIBUTE,
        "programs": sorted({a.study_program for a in applicants}),
        "n_admitted": int(sum(a.admit for a in applicants)),
        "tier_counts": _tier_counts(applicants),
        "base_dir": str(paths.base_dir),
    }
    (paths.base_dir / "cohort_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _tier_counts(applicants) -> dict:
    counts: dict[str, int] = {t: 0 for t in answers_mod.TIERS}
    for a in applicants:
        for tier in a.answer_tiers.values():
            counts[tier] = counts.get(tier, 0) + 1
    return counts
