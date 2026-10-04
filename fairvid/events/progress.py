"""Case files the progress manager reads and writes.

Each application is one JSON file. Consumers update it when a stage finishes.
The manager's HTTP and Kafka interfaces only read it (plus they answer
"how far along is this?").
"""

import fcntl
import json
import os
from pathlib import Path

from ..config import REPO_ROOT
from .topics import STAGE_ORDER


def progress_dir() -> Path:
    override = os.environ.get("FAIRVID_PROGRESS_DIR")
    path = Path(override) if override else REPO_ROOT / "var" / "progress"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(application_id: str) -> Path:
    safe = "".join(ch for ch in application_id if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        safe = "unknown"
    return progress_dir() / f"{safe}.json"


def _blank(application_id: str, email: str, name: str) -> dict:
    return {
        "application_id": application_id,
        "email": email,
        "name": name,
        "overall": "in_progress",
        "stages": {stage: {"status": "pending", "at": None} for stage in STAGE_ORDER},
    }


class ProgressStore:
    def apply(self, event: dict) -> dict:
        """Record one stage update and return the new snapshot."""
        application_id = event["application_id"]
        path = _path(application_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read()
            if raw.strip():
                case = json.loads(raw)
            else:
                case = _blank(application_id, event.get("email", ""), event.get("name", ""))
            if event.get("email"):
                case["email"] = event["email"]
            if event.get("name"):
                case["name"] = event["name"]
            stage = event.get("stage")
            if stage in case["stages"]:
                case["stages"][stage] = {
                    "status": event.get("status", "completed"),
                    "at": event.get("occurred_at"),
                }
            case["overall"] = _overall(case)
            if stage == "evaluation" and event.get("status") == "completed":
                decision = (event.get("payload") or {}).get("decision") or {}
                case["decision"] = decision.get("admit")
                case["probability"] = decision.get("probability")
            handle.seek(0)
            handle.truncate()
            json.dump(case, handle, indent=2)
            handle.write("\n")
            handle.flush()
        return self.snapshot(application_id)

    def snapshot(self, application_id: str) -> dict | None:
        path = _path(application_id)
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            case = json.loads(handle.read())
        stages = case["stages"]
        done = [name for name, info in stages.items() if info["status"] == "completed"]
        waiting = [name for name, info in stages.items() if info["status"] == "pending"]
        failed = [name for name, info in stages.items() if info["status"] == "failed"]
        case["completed_stages"] = done
        case["waiting_on"] = waiting
        case["failed_stages"] = failed
        case["percent"] = round(100 * len(done) / len(STAGE_ORDER))
        return case

    def list_ids(self) -> list[str]:
        return sorted(path.stem for path in progress_dir().glob("*.json"))


def _overall(case: dict) -> str:
    statuses = [info["status"] for info in case["stages"].values()]
    if any(status == "failed" for status in statuses):
        return "failed"
    # The case closes only after the email and the reconciliation audit are
    # both done. Reconciliation does not gate the decision, only the close.
    if all(status == "completed" for status in statuses):
        return "complete"
    return "in_progress"
