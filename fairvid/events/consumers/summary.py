"""Write an anonymised executive summary. Names are not copied into the text."""

from fairvid.events.handlers import handle_summary
from fairvid.events.topics import DOCUMENTS_PAGES_MERGED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-summary", [DOCUMENTS_PAGES_MERGED], handle_summary)


if __name__ == "__main__":
    main()
