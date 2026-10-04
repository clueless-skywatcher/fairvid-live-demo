"""Run one application through every consumer inside this process.

No broker is required. The same handlers are what the Kafka scripts call.

    python -m fairvid.events.local
"""

from .bus import MemoryBus
from .handlers import routes
from .messages import new_event
from .progress import ProgressStore
from .topics import PROGRESS


def run_application(event: dict, store: ProgressStore | None = None) -> dict:
    """Publish ``event`` on the intake topic and drain every follow-up."""
    store = store or ProgressStore()
    bus = MemoryBus()
    table = routes()
    # The caller passes an application.received event, or any event whose stage
    # is application.received. We always enter through the intake topic.
    from .topics import APPLICATION_RECEIVED
    bus.publish(APPLICATION_RECEIVED, event)
    while bus.pending():
        topic, incoming = bus.pop()
        if topic == PROGRESS:
            store.apply(incoming)
            continue
        for handler in table.get(topic, []):
            for next_topic, follow in handler(incoming):
                bus.publish(next_topic, follow)
    snapshot = store.snapshot(event["application_id"])
    if snapshot is None:
        raise RuntimeError(f"no progress recorded for {event['application_id']}")
    return snapshot


def main() -> None:
    event = new_event(
        "demo-1001",
        "application.received",
        "completed",
        {
            "gpa": 2.8,
            "test_score": 64,
            "english_score": 6.0,
            "work_experience_years": 0,
            "question": "Why this programme?",
            "transcript": (
                "I think the programme is good and important and I will try to do things."
            ),
        },
        email="ada@example.com",
        name="Ada Applicant",
    )
    snapshot = run_application(event)
    print(f"{snapshot['application_id']}: {snapshot['overall']} ({snapshot['percent']}%)")
    print(f"decision={snapshot.get('decision')} probability={snapshot.get('probability')}")
    print("waiting:", ", ".join(snapshot["waiting_on"]) or "none")


if __name__ == "__main__":
    main()
