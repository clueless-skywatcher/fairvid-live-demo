"""Extract the interview audio track."""

from fairvid.events.handlers import handle_audio
from fairvid.events.topics import INTERVIEW_RECORDED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-audio", [INTERVIEW_RECORDED], handle_audio)


if __name__ == "__main__":
    main()
