"""Layer 2: synthetic document images (a diploma and a grade transcript).

We draw the documents with Pillow from the applicant's record, then save the
exact text we printed as "ground truth". The OCR stage later reads the images
back, and we compare its output against that ground truth to score accuracy.

A light amount of noise and rotation is added so the images resemble real
scans rather than crisp screenshots.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import config
from .records import Applicant

# Page size in pixels (roughly A4 at ~110 DPI).
_W, _H = 900, 1160


def _font(size: int, bold: bool = False):
    """Load a TrueType font if we can find one, else fall back to the bundled
    bitmap font (which ignores size, but still renders)."""
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _scan_effect(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    """Add slight grain and a tiny rotation to mimic a scanned page."""
    arr = np.asarray(img.convert("L")).astype(np.int16)
    noise = rng.normal(0, 6, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr)
    angle = float(rng.uniform(-1.2, 1.2))
    return out.rotate(angle, expand=False, fillcolor=255)


def _grades_for(applicant: Applicant, rng: np.random.Generator) -> list[tuple[str, str]]:
    """Pick subjects for the program and assign letter grades that roughly
    track the applicant's GPA."""
    subjects = config.PROGRAM_SUBJECTS.get(applicant.study_program, ("Subject A", "Subject B"))
    chosen = list(rng.choice(subjects, size=min(6, len(subjects)), replace=False))
    letters = ["A", "A-", "B+", "B", "B-", "C+", "C"]
    # Higher GPA -> grades drawn from the better end of the list.
    center = int(np.clip((4.0 - applicant.gpa) / 4.0 * len(letters), 0, len(letters) - 1))
    rows = []
    for subj in chosen:
        idx = int(np.clip(center + rng.integers(-1, 2), 0, len(letters) - 1))
        rows.append((str(subj), letters[idx]))
    return rows


def render_documents(applicant: Applicant, paths: config.Paths,
                     rng: np.random.Generator) -> dict:
    """Render the diploma and transcript images for one applicant and return
    the ground-truth field values that were printed on them."""
    out_dir = paths.documents_dir(applicant.applicant_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    institution = str(rng.choice(config.INSTITUTIONS))
    grad_year = 2025 - int(rng.integers(0, 4))
    grades = _grades_for(applicant, rng)

    # --- Diploma -------------------------------------------------------------
    dip = Image.new("RGB", (_W, _H), "white")
    d = ImageDraw.Draw(dip)
    d.rectangle([30, 30, _W - 30, _H - 30], outline="black", width=4)
    d.text((_W // 2, 150), institution, fill="black", font=_font(40), anchor="mm")
    d.text((_W // 2, 230), "DIPLOMA OF GRADUATION", fill="black", font=_font(30), anchor="mm")
    d.text((_W // 2, 380), "This certifies that", fill="black", font=_font(24), anchor="mm")
    d.text((_W // 2, 440), applicant.name, fill="black", font=_font(46), anchor="mm")
    d.text((_W // 2, 540), f"has been awarded the degree in", fill="black", font=_font(24), anchor="mm")
    d.text((_W // 2, 600), applicant.study_program, fill="black", font=_font(32), anchor="mm")
    d.text((_W // 2, 720), f"Conferred in the year {grad_year}", fill="black", font=_font(24), anchor="mm")
    diploma_path = out_dir / "diploma.png"
    _scan_effect(dip, rng).save(diploma_path)

    # --- Transcript ----------------------------------------------------------
    tr = Image.new("RGB", (_W, _H), "white")
    t = ImageDraw.Draw(tr)
    t.text((60, 70), institution, fill="black", font=_font(30))
    t.text((60, 120), "ACADEMIC TRANSCRIPT", fill="black", font=_font(26))
    t.text((60, 180), f"Name: {applicant.name}", fill="black", font=_font(22))
    t.text((60, 215), f"Program: {applicant.study_program}", fill="black", font=_font(22))
    t.text((60, 250), f"Cumulative GPA: {applicant.gpa:.2f} / 4.00", fill="black", font=_font(22))
    t.line([60, 300, _W - 60, 300], fill="black", width=2)
    t.text((60, 320), "Subject", fill="black", font=_font(22))
    t.text((_W - 200, 320), "Grade", fill="black", font=_font(22))
    y = 370
    for subj, grade in grades:
        t.text((60, y), subj, fill="black", font=_font(22))
        t.text((_W - 200, y), grade, fill="black", font=_font(22))
        y += 45
    transcript_path = out_dir / "transcript.png"
    _scan_effect(tr, rng).save(transcript_path)

    return {
        "applicant_id": applicant.applicant_id,
        "name": applicant.name,
        "institution": institution,
        "study_program": applicant.study_program,
        "graduation_year": grad_year,
        "gpa": applicant.gpa,
        "grades": [{"subject": s, "grade": g} for s, g in grades],
        "images": {
            "diploma": str(diploma_path.relative_to(paths.base_dir)),
            "transcript": str(transcript_path.relative_to(paths.base_dir)),
        },
    }
