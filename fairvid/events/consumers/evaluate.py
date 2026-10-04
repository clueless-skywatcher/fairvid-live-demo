"""Wait until the document and interview branches have all reported, then score."""

from fairvid.events.handlers import handle_join, join_topics
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-evaluate", list(join_topics()), handle_join)


if __name__ == "__main__":
    main()
