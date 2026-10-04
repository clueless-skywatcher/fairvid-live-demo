"""The JSON object carried on every topic."""

from datetime import datetime, timezone
from uuid import uuid4


def new_event(
    application_id: str,
    stage: str,
    status: str,
    payload: dict | None = None,
    *,
    email: str = "",
    name: str = "",
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict:
    event_id = str(uuid4())
    return {
        "event_id": event_id,
        "application_id": str(application_id),
        "email": email,
        "name": name,
        "stage": stage,
        "status": status,
        "payload": dict(payload or {}),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id or event_id,
        "causation_id": causation_id,
    }


def child_event(parent: dict, stage: str, status: str, payload: dict) -> dict:
    """A follow-up event that keeps the same application and email."""
    return new_event(
        parent["application_id"],
        stage,
        status,
        payload,
        email=parent.get("email", ""),
        name=parent.get("name", ""),
        correlation_id=parent.get("correlation_id") or parent.get("event_id"),
        causation_id=parent.get("event_id"),
    )
