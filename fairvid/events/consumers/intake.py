"""Fan one received application out to the document track and the interview track."""

from fairvid.events.handlers import handle_intake
from fairvid.events.topics import APPLICATION_RECEIVED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-intake", [APPLICATION_RECEIVED], handle_intake)


if __name__ == "__main__":
    main()
