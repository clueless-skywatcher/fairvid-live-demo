"""Email the student the decision and the points they can still improve."""

from fairvid.events.handlers import handle_notify
from fairvid.events.topics import EVALUATION_COMPLETED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-notify", [EVALUATION_COMPLETED], handle_notify)


if __name__ == "__main__":
    main()
