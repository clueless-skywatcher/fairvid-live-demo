"""Grade one transcript for relevance, clarity, and scripted-answer flags."""

from fairvid.events.handlers import handle_grade
from fairvid.events.topics import INTERVIEW_TRANSCRIPT_COMPLETED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-grade", [INTERVIEW_TRANSCRIPT_COMPLETED], handle_grade)


if __name__ == "__main__":
    main()
