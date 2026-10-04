"""Print the topic list and the command that starts each consumer."""

from . import topics
from .topics import STAGE_ORDER

COMMANDS = (
    ("fairvid.events.consumers.intake", topics.APPLICATION_RECEIVED),
    ("fairvid.events.consumers.ocr", topics.DOCUMENTS_UPLOADED),
    ("fairvid.events.consumers.pages", topics.DOCUMENTS_OCR_COMPLETED),
    ("fairvid.events.consumers.summary", topics.DOCUMENTS_PAGES_MERGED),
    ("fairvid.events.consumers.reconcile", topics.DOCUMENTS_SUMMARY_COMPLETED),
    ("fairvid.events.consumers.eligibility", topics.DOCUMENTS_SUMMARY_COMPLETED),
    ("fairvid.events.consumers.audio", topics.INTERVIEW_RECORDED),
    ("fairvid.events.consumers.transcribe", topics.INTERVIEW_AUDIO_EXTRACTED),
    ("fairvid.events.consumers.grade", topics.INTERVIEW_TRANSCRIPT_COMPLETED),
    ("fairvid.events.consumers.prosody", topics.INTERVIEW_AUDIO_EXTRACTED),
    ("fairvid.events.consumers.behaviour", topics.INTERVIEW_RECORDED),
    ("fairvid.events.consumers.frame", topics.INTERVIEW_RECORDED),
    ("fairvid.events.consumers.evaluate", "join of the five completion topics"),
    ("fairvid.events.consumers.notify", topics.EVALUATION_COMPLETED),
    ("fairvid.events.manager", f"{topics.MANAGER_REQUEST} plus HTTP :5001"),
)


def main() -> None:
    print("Stages:", ", ".join(STAGE_ORDER))
    print()
    for module, topic in COMMANDS:
        print(f"python -m {module}")
        print(f"    {topic}")


if __name__ == "__main__":
    main()