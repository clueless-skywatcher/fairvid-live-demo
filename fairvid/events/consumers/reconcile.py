"""Vote across model summaries. This audit step does not block the decision."""

from fairvid.events.handlers import handle_reconcile
from fairvid.events.topics import DOCUMENTS_SUMMARY_COMPLETED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-reconcile", [DOCUMENTS_SUMMARY_COMPLETED], handle_reconcile)


if __name__ == "__main__":
    main()
