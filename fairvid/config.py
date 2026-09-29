"""Settings shared by the whole package: where files go, the list of study
programs, and the demographic categories used for the fairness tests.

The folders we create on disk use the same names as the Google Drive folders in
WORKFLOW.md. Because the names match, the generated files can be read by the
existing notebooks without changing anything. By default everything is written
to a local folder, but you can point `base_dir` at a mounted Google Drive
instead (e.g. /content/drive/MyDrive/colab-output/...).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# The repo root is one folder up from this package.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Top-level folder name, taken from WORKFLOW.md:
#   .../dream_applicant_application/{applicant_id}/...
APPLICATION_ROOT_NAME = "dream_applicant_application"

# Folder names the existing notebooks already use. We keep them spelled exactly
# the same (even where the original had quirks) so the notebooks can read our
# generated files directly.
DOCUMENTS_IMAGE_DIR = "documents_image"
TRANSCRIPTS_DIR = "video_interviews_audio_transcriptions_text"

# Perceptual-output folders, named exactly as the Colab notebooks write them, so
# the same fusion code reads either our generated artifacts or the real notebook
# output. MediaPipe behaviour JSON and the vision-LLM frame descriptions.
BLENDSHAPE_DIR = "video_interviews_blendshape_files"   # MediaPipe behaviour JSON
VLM_MODEL = "gemma3:12b"                                # the frame-description model
FRAME_TEXT_DIR = f"video_frame_text_{VLM_MODEL}"        # Gemma frame descriptions

# New folders that only the generator writes to. They hold the "correct
# answers" (ground truth) we compare the pipeline's output against.
GROUND_TRUTH_DIR = "ground_truth"
DOC_GROUNDTRUTH_DIR = "documents_image_groundtruth"


@dataclass(frozen=True)
class Paths:
    """Builds the folder paths for the whole cohort and for each applicant."""

    base_dir: Path = REPO_ROOT / "synthetic_data"

    @property
    def application_root(self) -> Path:
        return self.base_dir / APPLICATION_ROOT_NAME

    def applicant_dir(self, applicant_id: str) -> Path:
        return self.application_root / applicant_id

    def documents_dir(self, applicant_id: str) -> Path:
        return self.applicant_dir(applicant_id) / DOCUMENTS_IMAGE_DIR

    def doc_groundtruth_dir(self, applicant_id: str) -> Path:
        return self.applicant_dir(applicant_id) / DOC_GROUNDTRUTH_DIR

    def transcripts_dir(self, applicant_id: str, study_program: str) -> Path:
        return self.applicant_dir(applicant_id) / TRANSCRIPTS_DIR / slugify(study_program)

    def blendshape_dir(self, applicant_id: str, study_program: str) -> Path:
        return self.applicant_dir(applicant_id) / BLENDSHAPE_DIR / slugify(study_program)

    def frame_text_dir(self, applicant_id: str, study_program: str) -> Path:
        return self.applicant_dir(applicant_id) / FRAME_TEXT_DIR / slugify(study_program)

    def ground_truth_dir(self, applicant_id: str) -> Path:
        return self.applicant_dir(applicant_id) / GROUND_TRUTH_DIR


# --- Demographic categories (the "protected attributes" for fairness) --------
# These are made-up groups. They do not describe any real person. We only use
# them to measure whether the model treats groups differently, and to test ways
# of reducing that difference.
GENDERS = ("female", "male", "nonbinary")
REGIONS = ("region_a", "region_b", "region_c", "region_d")
AGE_RANGE = (21, 38)

# The attribute the generator uses when it deliberately adds an unfair gap
# between groups, so the fairness experiments have something to detect and fix.
DEFAULT_PROTECTED_ATTRIBUTE = "region"

# Subjects for each program, used to fill in the synthetic transcripts/diplomas.
PROGRAM_SUBJECTS: dict[str, tuple[str, ...]] = {
    "Biomedical Engineering": (
        "Human Physiology", "Biomechanics", "Medical Imaging", "Biomaterials",
        "Signal Processing", "Tissue Engineering", "Biostatistics", "Bioethics",
    ),
    "Aerospace Engineering": (
        "Fluid Dynamics", "Aerodynamics", "Propulsion Systems", "Materials Science",
        "Flight Mechanics", "Control Systems", "Thermodynamics", "Structural Analysis",
    ),
    "Electronics Engineering": (
        "Digital Logic", "Analog Circuits", "Microprocessors", "Signal Processing",
        "Semiconductor Physics", "Embedded Systems", "Communication Systems", "VLSI Design",
    ),
    "Environmental Engineering and Management": (
        "Environmental Chemistry", "Waste Management", "Water Resources", "Life Cycle Assessment",
        "Renewable Energy", "Environmental Policy", "Hydrology", "Sustainability Science",
    ),
}

# Made-up universities to print on the diplomas.
INSTITUTIONS = (
    "Northgate Institute of Technology",
    "Meridian State University",
    "Cordoba Polytechnic",
    "Lakeside University of Applied Sciences",
    "Aurelia Technical University",
)

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Turn a label into a safe lowercase file/folder name (drops emoji)."""
    text = text.encode("ascii", "ignore").decode("ascii")
    return _slug_re.sub("_", text.lower()).strip("_")


def normalize_program(study_program: str) -> str:
    """Take a raw program name from the TSV (which may include an emoji or a
    prefix like "Master's degree in") and return the matching key from
    PROGRAM_SUBJECTS. If nothing matches, return the cleaned-up name."""
    cleaned = study_program.encode("ascii", "ignore").decode("ascii").strip()
    for key in PROGRAM_SUBJECTS:
        if key.lower() in cleaned.lower():
            return key
    return cleaned
