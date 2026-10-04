"""Read uploaded document images and record what the OCR step saw."""

from fairvid.events.handlers import handle_ocr
from fairvid.events.topics import DOCUMENTS_UPLOADED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-ocr", [DOCUMENTS_UPLOADED], handle_ocr)


if __name__ == "__main__":
    main()
