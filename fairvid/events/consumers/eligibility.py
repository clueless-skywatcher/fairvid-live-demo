"""Check study level and country codes from the anonymised summary."""

from fairvid.events.handlers import handle_eligibility
from fairvid.events.topics import DOCUMENTS_SUMMARY_COMPLETED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-eligibility", [DOCUMENTS_SUMMARY_COMPLETED], handle_eligibility)


if __name__ == "__main__":
    main()
