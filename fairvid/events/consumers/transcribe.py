"""Turn interview audio into a transcript."""

from fairvid.events.handlers import handle_transcribe
from fairvid.events.topics import INTERVIEW_AUDIO_EXTRACTED
from fairvid.events.worker import serve


def main() -> None:
    serve("fairvid-transcribe", [INTERVIEW_AUDIO_EXTRACTED], handle_transcribe)


if __name__ == "__main__":
    main()
