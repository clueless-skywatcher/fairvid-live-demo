"""Merge page-wise document text into one file per document.

This is the logic from `merge_document_pages.ipynb`. Page-level OCR or
vision-LLM files are named like ``Passport.pdf (page 1).txt``. They are grouped
by the original document name, sorted, and concatenated. The text itself is
not rewritten.
"""

import re
from collections import defaultdict
from pathlib import Path

from .. import config

# "Passport.pdf (page 2).txt" -> document id "Passport.pdf"
_PAGE_SUFFIX = re.compile(r"\s\(page \d+\)\.txt$")


def document_id(filename: str) -> str:
    """Strip a `` (page N).txt`` suffix, or a plain ``.txt`` extension."""
    name = Path(filename).name
    if _PAGE_SUFFIX.search(name):
        return _PAGE_SUFFIX.sub("", name)
    if name.lower().endswith(".txt"):
        return name[:-4]
    return name


def group_page_files(file_list: list[str]) -> dict[str, list[str]]:
    """Group page files that belong to the same original document."""
    documents: dict[str, list[str]] = defaultdict(list)
    for filename in file_list:
        documents[document_id(filename)].append(filename)
    return dict(documents)


def page_sort_key(path: str) -> tuple:
    """Order ``(page N)`` files by page number, then by name."""
    match = re.search(r"\(page (\d+)\)", Path(path).name)
    page = int(match.group(1)) if match else 0
    return (page, Path(path).name)


def concatenate_pages(pages: list[str]) -> str:
    """Read page files in page order and join them with a blank line."""
    chunks = []
    for page_path in sorted(pages, key=page_sort_key):
        chunks.append(Path(page_path).read_text(encoding="utf-8"))
    return "\n".join(chunks)


def merge_applicant_pages(
    applicant_dir: Path,
    prefix: str = config.LLM_PAGE_TEXT_PREFIX,
    *,
    skip_existing: bool = True,
) -> list[Path]:
    """Merge every ``{prefix}*`` folder under one applicant.

    Writes ``{source_folder}_doc/{document}.txt``. Returns the output files
    that were written on this call.
    """
    written: list[Path] = []
    applicant_dir = Path(applicant_dir)
    for source in sorted(applicant_dir.glob(f"{prefix}*")):
        if not source.is_dir() or source.name.endswith("_doc"):
            continue
        output_dir = applicant_dir / f"{source.name}_doc"
        if skip_existing and output_dir.exists():
            continue
        files = [str(f) for f in source.iterdir() if f.is_file()]
        if not files:
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        for doc_id, pages in group_page_files(files).items():
            out = output_dir / f"{Path(doc_id).name}.txt"
            out.write_text(concatenate_pages(pages), encoding="utf-8")
            written.append(out)
    return written
