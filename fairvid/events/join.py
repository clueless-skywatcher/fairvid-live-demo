"""Wait until every required branch has reported, then hand back one payload."""

import fcntl
import json
import os
from pathlib import Path

from ..config import REPO_ROOT
from .topics import JOIN_STAGES


def join_dir() -> Path:
    override = os.environ.get("FAIRVID_JOIN_DIR")
    path = Path(override) if override else REPO_ROOT / "var" / "joins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def note_stage(directory: Path, event: dict) -> dict | None:
    """Store this stage. Return the merged payload once every join stage is present."""
    application_id = event["application_id"]
    safe = "".join(ch for ch in application_id if ch.isalnum() or ch in ("-", "_")) or "unknown"
    path = Path(directory) / f"{safe}.json"
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        raw = handle.read()
        state = json.loads(raw) if raw.strip() else {"stages": {}, "payloads": {}}
        stage = event["stage"]
        state["stages"][stage] = event.get("status")
        state["payloads"][stage] = event.get("payload") or {}
        handle.seek(0)
        handle.truncate()
        json.dump(state, handle)
        handle.flush()
        if any(state["stages"].get(name) != "completed" for name in JOIN_STAGES):
            return None
        merged: dict = {}
        for name in JOIN_STAGES:
            merged.update(state["payloads"].get(name) or {})
        return merged
