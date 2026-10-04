"""Run one consumer against Kafka until the process is stopped."""

from .bus import kafka_bus
from .progress import ProgressStore


def serve(group: str, topics: list[str], handler) -> None:
    store = ProgressStore()
    bus = kafka_bus()

    def wrapped(event: dict):
        followups = handler(event)
        for _topic, follow in followups:
            if follow.get("application_id") and follow.get("stage"):
                store.apply(follow)
        return followups

    bus.consume_forever(topics, group, wrapped)
