"""Progress manager.

Staff ask this process how far an application has got. Two ways to ask:

- HTTP ``GET /applications/<id>`` or ``POST /applications/<id>/progress``
- A Kafka message on ``admissions.manager.request``. The reply is published on
  ``admissions.manager.response`` with the same ``correlation_id``.

    python -m fairvid.events.manager

The HTTP server always starts. The Kafka listener starts when
``FAIRVID_KAFKA_BOOTSTRAP`` is set. Progress files are updated by the
consumers themselves, so a request is answered from disk.
"""

import os
import threading

from flask import Flask, jsonify, request

from .bus import kafka_bootstrap, kafka_bus
from .handlers import handle_manager_request
from .messages import new_event
from .progress import ProgressStore
from .topics import APPLICATION_RECEIVED, MANAGER_REQUEST


def create_app(store: ProgressStore | None = None) -> Flask:
    store = store or ProgressStore()
    app = Flask("fairvid.manager")

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/applications/<application_id>")
    def get_progress(application_id: str):
        snapshot = store.snapshot(application_id)
        if snapshot is None:
            return jsonify({"error": "unknown application", "application_id": application_id}), 404
        return jsonify(snapshot)

    @app.post("/applications/<application_id>/progress")
    def request_progress(application_id: str):
        """A progress request. The body is optional. The answer is the case file."""
        snapshot = store.snapshot(application_id)
        if snapshot is None:
            return jsonify({"error": "unknown application", "application_id": application_id}), 404
        return jsonify({"requested": True, "progress": snapshot})

    @app.post("/applications")
    def open_application():
        """Publish a new application onto the intake topic."""
        body = request.get_json(force=True, silent=True) or {}
        application_id = body.get("application_id")
        email = body.get("email")
        if not application_id or not email:
            return jsonify({"error": "application_id and email are required"}), 400
        event = new_event(
            application_id,
            "application.received",
            "completed",
            {key: value for key, value in body.items() if key not in {"application_id", "email", "name"}},
            email=email,
            name=body.get("name", ""),
        )
        if not kafka_bootstrap():
            return jsonify({
                "error": "Kafka is not configured. Set FAIRVID_KAFKA_BOOTSTRAP, "
                         "or run python -m fairvid.events.local for one in-process case.",
            }), 503
        kafka_bus().publish(APPLICATION_RECEIVED, event)
        store.apply(event)
        return jsonify({"published": APPLICATION_RECEIVED, "application_id": application_id}), 202

    return app


def listen_for_requests(store: ProgressStore) -> None:
    bus = kafka_bus()

    def handler(event: dict):
        if event.get("stage") == "manager.request" or event.get("application_id"):
            return handle_manager_request(event, store)
        return []

    bus.consume_forever([MANAGER_REQUEST], "fairvid-manager", handler)


def main() -> None:
    store = ProgressStore()
    if kafka_bootstrap():
        threading.Thread(target=listen_for_requests, args=(store,), daemon=True).start()
    host = os.environ.get("FAIRVID_HOST", "127.0.0.1")
    port = int(os.environ.get("FAIRVID_MANAGER_PORT", "5001"))
    print(f"FAIR-VID progress manager at http://{host}:{port}")
    create_app(store).run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
