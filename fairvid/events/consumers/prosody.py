"""Measure tempo, pauses, and pitch on the extracted audio."""

from fairvid.events.handlers import handle_prosody
from fairvid.events.topics import INTERVIEW_AUDIO_EXTRACTED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-prosody", [INTERVIEW_AUDIO_EXTRACTED], handle_prosody)


if __name__ == "__main__":
    main()
