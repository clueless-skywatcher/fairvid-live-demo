"""Describe one interview frame and flag a distracting setting."""

from fairvid.events.handlers import handle_frame
from fairvid.events.topics import INTERVIEW_RECORDED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-frame", [INTERVIEW_RECORDED], handle_frame)


if __name__ == "__main__":
    main()
