"""The admissions flow completes without a Kafka broker and writes the letter."""

import json
import os
import tempfile
from pathlib import Path

from fairvid.events.emailer import render_letter
from fairvid.events.handlers import handle_manager_request
from fairvid.events.local import run_application
from fairvid.events.manager import create_app
from fairvid.events.messages import new_event
from fairvid.events.progress import ProgressStore


def test_application_reaches_a_letter_and_the_manager_can_report_it():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        os.environ["FAIRVID_PROGRESS_DIR"] = str(root / "progress")
        os.environ["FAIRVID_JOIN_DIR"] = str(root / "joins")
        os.environ["FAIRVID_OUTBOX"] = str(root / "outbox")
        os.environ.pop("FAIRVID_SMTP_HOST", None)

        event = new_event(
            "18190_27580",
            "application.received",
            "completed",
            {
                "gpa": 2.4,
                "test_score": 58,
                "english_score": 5.5,
                "work_experience_years": 0,
                "question": "Why this programme?",
                "transcript": "It is good and important and I will try to do things.",
            },
            email="ada@example.com",
            name="Ada Applicant",
        )
        store = ProgressStore()
        snapshot = run_application(event, store)

        assert snapshot["overall"] == "complete"
        assert snapshot["percent"] == 100
        assert snapshot["waiting_on"] == []
        assert snapshot["decision"] in (True, False)
        letter = root / "outbox" / "18190_27580.txt"
        text = letter.read_text(encoding="utf-8")
        assert "To: ada@example.com" in text
        assert "Decision:" in text
        assert "Where to improve" in text

        client = create_app(store).test_client()
        got = client.get("/applications/18190_27580")
        assert got.status_code == 200
        body = got.get_json()
        assert body["overall"] == "complete"
        asked = client.post("/applications/18190_27580/progress", json={})
        assert asked.status_code == 200
        assert asked.get_json()["progress"]["application_id"] == "18190_27580"
        missing = client.get("/applications/does-not-exist")
        assert missing.status_code == 404

        reply_topic, reply = handle_manager_request(
            new_event("18190_27580", "manager.request", "completed", email="staff@example.com"),
            store,
        )[0]
        assert reply_topic.endswith("manager.response")
        assert reply["payload"]["progress"]["percent"] == 100
        assert reply["correlation_id"]

        saved = json.loads((root / "progress" / "18190_27580.json").read_text(encoding="utf-8"))
        assert saved["stages"]["notification"]["status"] == "completed"


def test_letter_names_an_interview_improvement():
    event = new_event(
        "1",
        "evaluation",
        "completed",
        {
            "decision": {"admit": False, "probability": 0.31},
            "improvements": ["Look at the camera instead of down at notes."],
            "record_notes": ["GPA is already on your record. This flow does not change it."],
        },
        email="ada@example.com",
        name="Ada",
    )
    _subject, body = render_letter(event)
    assert "Not admitted" in body
    assert "Look at the camera" in body
    assert "GPA is already on your record" in body
