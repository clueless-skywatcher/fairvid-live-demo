"""Loads the interview questions, grouped by study program.

It reads the TSV from the fair-vid GitHub repo (the same file the RecordVideo
notebook uses) and caches it locally so repeated runs work offline.
"""

import csv
import urllib.request
from collections import defaultdict
from pathlib import Path

from .. import config

QUESTIONS_URL = (
    "https://raw.githubusercontent.com/fair-vid/fair-vid-synthetic-data/"
    "main/interview_questionnaires/interview_questions_v1.tsv"
)
_CACHE = config.REPO_ROOT / "synthetic_data" / "_cache" / "interview_questions_v1.tsv"


def _download(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(QUESTIONS_URL, dest)


def load_questions(tsv_path: Path | None = None) -> dict[str, list[tuple[int, str, int]]]:
    """Return {raw_program_label: [(index, question, time_seconds), ...]}.

    Downloads and caches the TSV on first use unless a local path is given.
    """
    path = tsv_path or _CACHE
    if not path.exists():
        _download(path)

    by_program: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        counters: dict[str, int] = defaultdict(int)
        for row in reader:
            program = row["Study_Program"].strip()
            idx = counters[program]
            counters[program] += 1
            time_s = int(row.get("Time") or 60)
            by_program[program].append((idx, row["Question"].strip(), time_s))
    return dict(by_program)
