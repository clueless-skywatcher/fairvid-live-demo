"""Publish and consume JSON events.

``MemoryBus`` is an in-process queue used by tests and by
``python -m fairvid.events.local``. ``KafkaBus`` talks to a real broker.
Set ``FAIRVID_KAFKA_BOOTSTRAP`` (for example ``localhost:9092``).
"""

import json
import os
from collections import deque


class MemoryBus:
    """A FIFO of ``(topic, event)`` pairs. One process, no broker."""

    def __init__(self):
        self._queue: deque[tuple[str, dict]] = deque()

    def publish(self, topic: str, event: dict) -> None:
        self._queue.append((topic, event))

    def pending(self) -> bool:
        return bool(self._queue)

    def pop(self) -> tuple[str, dict]:
        return self._queue.popleft()


class KafkaBus:
    """kafka-python producer and consumer. Created lazily so imports stay light."""

    def __init__(self, bootstrap: str):
        self.bootstrap = bootstrap
        self._producer = None

    def producer(self):
        if self._producer is None:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap.split(","),
                key_serializer=lambda key: key.encode("utf-8") if key else None,
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            )
        return self._producer

    def publish(self, topic: str, event: dict) -> None:
        key = event.get("application_id") or event.get("correlation_id")
        self.producer().send(topic, key=key, value=event)
        self.producer().flush()

    def consume_forever(self, topics: list[str], group: str, handler) -> None:
        from kafka import KafkaConsumer
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap.split(","),
            group_id=group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        )
        print(f"listening on {', '.join(topics)} as {group}")
        for record in consumer:
            followups = handler(record.value)
            for topic, event in followups:
                self.publish(topic, event)
            consumer.commit()


def kafka_bootstrap() -> str | None:
    value = os.environ.get("FAIRVID_KAFKA_BOOTSTRAP", "").strip()
    return value or None


def kafka_bus() -> KafkaBus:
    bootstrap = kafka_bootstrap()
    if not bootstrap:
        raise SystemExit(
            "Set FAIRVID_KAFKA_BOOTSTRAP, for example localhost:9092, "
            "before starting a consumer."
        )
    return KafkaBus(bootstrap)
