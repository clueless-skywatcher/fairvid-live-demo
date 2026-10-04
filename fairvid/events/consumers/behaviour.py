"""Measure gaze, smile, and head motion on the interview video."""

from fairvid.events.handlers import handle_behaviour
from fairvid.events.topics import INTERVIEW_RECORDED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-behaviour", [INTERVIEW_RECORDED], handle_behaviour)


if __name__ == "__main__":
    main()
