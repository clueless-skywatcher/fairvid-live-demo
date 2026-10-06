"""What each consumer does when a message arrives.

Handlers do not talk to Kafka. They return the next ``(topic, event)`` pairs.
The worker publishes those pairs. Payload keys are copied forward so the
evaluation join still has the academic record from the first message.
"""

from pathlib import Path

from ..pipeline.eligibility import extract_country_codes, normalize_awards_abbr
from ..pipeline.pages import merge_applicant_pages
from .emailer import send_letter
from .evaluate import decide, features_from_payload, improvements
from .join import join_dir, note_stage
from .messages import child_event
from .topics import (
    DOCUMENTS_ELIGIBILITY_COMPLETED,
    DOCUMENTS_OCR_COMPLETED,
    DOCUMENTS_PAGES_MERGED,
    DOCUMENTS_RECONCILED,
    DOCUMENTS_SUMMARY_COMPLETED,
    DOCUMENTS_UPLOADED,
    EVALUATION_COMPLETED,
    INTERVIEW_AUDIO_EXTRACTED,
    INTERVIEW_BEHAVIOUR_COMPLETED,
    INTERVIEW_FRAME_COMPLETED,
    INTERVIEW_GRADE_COMPLETED,
    INTERVIEW_PROSODY_COMPLETED,
    INTERVIEW_RECORDED,
    INTERVIEW_TRANSCRIPT_COMPLETED,
    NOTIFICATION_SENT,
    PROGRESS,
)


def _carry(event: dict, stage: str, extra: dict, topic: str) -> list[tuple[str, dict]]:
    payload = {**event.get("payload", {}), **extra, "stage": stage}
    completed = child_event(event, stage, "completed", payload)
    return [(topic, completed), (PROGRESS, completed)]


def _fail(event: dict, stage: str, exc: Exception) -> list[tuple[str, dict]]:
    payload = {**event.get("payload", {}), "error": f"{type(exc).__name__}: {exc}"}
    failed = child_event(event, stage, "failed", payload)
    return [(PROGRESS, failed)]


def handle_intake(event: dict) -> list[tuple[str, dict]]:
    """Open both tracks. Also mark the application itself as received."""
    received = child_event(event, "application.received", "completed", dict(event.get("payload") or {}))
    documents = child_event(event, "documents.uploaded", "completed", dict(event.get("payload") or {}))
    interview = child_event(event, "interview.recorded", "completed", dict(event.get("payload") or {}))
    return [
        (PROGRESS, received),
        (DOCUMENTS_UPLOADED, documents),
        (INTERVIEW_RECORDED, interview),
    ]


def handle_ocr(event: dict) -> list[tuple[str, dict]]:
    folder = event.get("payload", {}).get("applicant_dir")
    images = []
    if folder and Path(folder).is_dir():
        images = [
            path.name for path in Path(folder).rglob("*")
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"}
        ]
    return _carry(event, "documents.ocr", {
        "ocr": {"image_count": len(images), "images": images[:20]},
    }, DOCUMENTS_OCR_COMPLETED)


def handle_pages(event: dict) -> list[tuple[str, dict]]:
    folder = event.get("payload", {}).get("applicant_dir")
    written = []
    if folder:
        written = [str(path) for path in merge_applicant_pages(Path(folder))]
    return _carry(event, "documents.pages", {
        "pages": {"merged_files": written},
    }, DOCUMENTS_PAGES_MERGED)


def handle_summary(event: dict) -> list[tuple[str, dict]]:
    """A short anonymised summary. Names from the event are not copied in."""
    payload = event.get("payload") or {}
    awards = normalize_awards_abbr(payload.get("awards_abbr", "Bachelor"))
    text = (
        f"The applicant seeks a {awards} place. "
        f"Recorded GPA {payload.get('gpa', 'n/a')}, "
        f"test score {payload.get('test_score', 'n/a')}, "
        f"English score {payload.get('english_score', 'n/a')}."
    )
    return _carry(event, "documents.summary", {
        "summary_markdown": text,
        "awards_abbr": awards,
    }, DOCUMENTS_SUMMARY_COMPLETED)


def handle_reconcile(event: dict) -> list[tuple[str, dict]]:
    """Audit step. A missing second model is a completed vote with nothing to compare."""
    return _carry(event, "documents.reconcile", {
        "reconcile": {"method": "nothing_to_compare"},
    }, DOCUMENTS_RECONCILED)


def handle_eligibility(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    summary = payload.get("summary_markdown") or ""
    awards = normalize_awards_abbr(payload.get("awards_abbr", "Bachelor"))
    return _carry(event, "documents.eligibility", {
        "eligibility": {
            "awards_abbr": awards,
            "country_codes": extract_country_codes(summary),
            "summary_present": bool(summary),
        },
    }, DOCUMENTS_ELIGIBILITY_COMPLETED)


def handle_audio(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    audio_path = payload.get("audio_path")
    video_path = payload.get("video_path")
    if not audio_path and video_path:
        try:
            from ..webapp.process_video import extract_audio
            dest = str(Path(video_path).with_suffix(".wav"))
            if extract_audio(Path(video_path), Path(dest)):
                audio_path = dest
        except Exception:
            audio_path = None
    return _carry(event, "interview.audio", {"audio_path": audio_path}, INTERVIEW_AUDIO_EXTRACTED)


def handle_transcribe(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    transcript = payload.get("transcript")
    if not transcript and payload.get("audio_path"):
        try:
            from ..webapp.process_video import transcribe
            transcript = transcribe(Path(payload["audio_path"]))
        except Exception as exc:
            return _fail(event, "interview.transcript", exc)
    return _carry(event, "interview.transcript", {
        "transcript": transcript or "",
    }, INTERVIEW_TRANSCRIPT_COMPLETED)


def handle_grade(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    transcript = payload.get("transcript") or ""
    question = payload.get("question") or ""
    try:
        from ..pipeline.grader import audit_transcript
        grade = audit_transcript(question, transcript) if transcript else None
    except Exception as exc:
        return _fail(event, "interview.grade", exc)
    if grade:
        extra = {
            "grade": grade,
            "interview_overall_mean": float(grade["overall_score"]),
            "interview_relevance_mean": float(grade["metrics"]["relevance_score"]),
            "interview_ai_flag_rate": 1.0 if grade["ai_script_detection"]["is_likely_reading_llm_text"] else 0.0,
        }
    else:
        extra = {"grade": None}
    return _carry(event, "interview.grade", extra, INTERVIEW_GRADE_COMPLETED)


def handle_prosody(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    affect = None
    if payload.get("audio_path"):
        try:
            from ..pipeline.audio_affect import analyze_audio
            affect = analyze_audio(payload["audio_path"], emotions=False)
        except Exception as exc:
            return _fail(event, "interview.prosody", exc)
    return _carry(event, "interview.prosody", {"prosody": affect}, INTERVIEW_PROSODY_COMPLETED)


def handle_behaviour(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    metrics = None
    if payload.get("video_path"):
        try:
            from ..pipeline.behaviour_video import analyse_video
            metrics = analyse_video(payload["video_path"])
        except Exception as exc:
            return _fail(event, "interview.behaviour", exc)
    extra = {"behaviour": metrics}
    if metrics:
        extra["behaviour_composite"] = float(metrics.get("Composite score", 70))
        extra["behaviour_reading_prob"] = float(metrics.get("Reading Prob", 20))
        extra["behaviour_smile"] = float(metrics.get("Smile Frequency", 20))
    return _carry(event, "interview.behaviour", extra, INTERVIEW_BEHAVIOUR_COMPLETED)


def handle_frame(event: dict) -> list[tuple[str, dict]]:
    payload = event.get("payload") or {}
    description = None
    distraction = None
    if payload.get("frame_path"):
        try:
            from ..config import DISTRACTION_KEYWORDS
            from ..pipeline.vlm import describe_image
            description = describe_image(payload["frame_path"])
            text = (description.get("text") or "").lower()
            distraction = 1.0 if any(word in text for word in DISTRACTION_KEYWORDS) else 0.0
        except Exception as exc:
            return _fail(event, "interview.frame", exc)
    extra = {"frame_description": description}
    if distraction is not None:
        extra["visual_distraction"] = distraction
    return _carry(event, "interview.frame", extra, INTERVIEW_FRAME_COMPLETED)


def handle_join(event: dict) -> list[tuple[str, dict]]:
    """Remember one finished branch. Score only when every required branch is in."""
    ready = note_stage(join_dir(), event)
    if ready is None:
        return [(PROGRESS, child_event(event, event["stage"], "completed", event.get("payload") or {}))]
    features = features_from_payload(ready)
    decision = decide(features)
    advice, notes = improvements(features)
    payload = {
        **ready,
        "decision": decision,
        "improvements": advice,
        "record_notes": notes,
    }
    completed = child_event(event, "evaluation", "completed", payload)
    return [(EVALUATION_COMPLETED, completed), (PROGRESS, completed)]


def handle_notify(event: dict) -> list[tuple[str, dict]]:
    try:
        receipt = send_letter(event)
    except Exception as exc:
        return _fail(event, "notification", exc)
    payload = {**event.get("payload", {}), "email_receipt": {
        "to": receipt["to"],
        "subject": receipt["subject"],
        "transport": receipt["transport"],
        "path": receipt.get("path"),
    }}
    completed = child_event(event, "notification", "completed", payload)
    return [(NOTIFICATION_SENT, completed), (PROGRESS, completed)]


def handle_manager_request(event: dict, store) -> list[tuple[str, dict]]:
    from .topics import MANAGER_RESPONSE
    snapshot = store.snapshot(event["application_id"])
    reply = child_event(event, "manager.response", "completed", {"progress": snapshot})
    reply["correlation_id"] = event.get("correlation_id") or event.get("event_id")
    return [(MANAGER_RESPONSE, reply)]


# topic -> handlers. Summary and audio each have two subscribers.
def routes() -> dict[str, list]:
    from .topics import (
        APPLICATION_RECEIVED,
        DOCUMENTS_OCR_COMPLETED,
        DOCUMENTS_PAGES_MERGED,
        DOCUMENTS_SUMMARY_COMPLETED,
        DOCUMENTS_UPLOADED,
        EVALUATION_COMPLETED,
        INTERVIEW_AUDIO_EXTRACTED,
        INTERVIEW_BEHAVIOUR_COMPLETED,
        INTERVIEW_FRAME_COMPLETED,
        INTERVIEW_GRADE_COMPLETED,
        INTERVIEW_PROSODY_COMPLETED,
        INTERVIEW_RECORDED,
        INTERVIEW_TRANSCRIPT_COMPLETED,
    )
    return {
        APPLICATION_RECEIVED: [handle_intake],
        DOCUMENTS_UPLOADED: [handle_ocr],
        DOCUMENTS_OCR_COMPLETED: [handle_pages],
        DOCUMENTS_PAGES_MERGED: [handle_summary],
        DOCUMENTS_SUMMARY_COMPLETED: [handle_reconcile, handle_eligibility],
        INTERVIEW_RECORDED: [handle_audio, handle_behaviour, handle_frame],
        INTERVIEW_AUDIO_EXTRACTED: [handle_transcribe, handle_prosody],
        INTERVIEW_TRANSCRIPT_COMPLETED: [handle_grade],
        EVALUATION_COMPLETED: [handle_notify],
        **{stage_topic: [handle_join] for stage_topic in (
            DOCUMENTS_ELIGIBILITY_COMPLETED,
            INTERVIEW_GRADE_COMPLETED,
            INTERVIEW_PROSODY_COMPLETED,
            INTERVIEW_BEHAVIOUR_COMPLETED,
            INTERVIEW_FRAME_COMPLETED,
        )},
    }


def join_topics() -> tuple[str, ...]:
    return (
        DOCUMENTS_ELIGIBILITY_COMPLETED,
        INTERVIEW_GRADE_COMPLETED,
        INTERVIEW_PROSODY_COMPLETED,
        INTERVIEW_BEHAVIOUR_COMPLETED,
        INTERVIEW_FRAME_COMPLETED,
    )
