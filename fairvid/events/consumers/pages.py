"""Merge page-wise document text into one file per document."""

from fairvid.events.handlers import handle_pages
from fairvid.events.topics import DOCUMENTS_OCR_COMPLETED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-pages", [DOCUMENTS_OCR_COMPLETED], handle_pages)


if __name__ == "__main__":
    main()
