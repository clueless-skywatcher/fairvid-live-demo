"""Send the decision letter, or file it when no mail server is configured.

SMTP is used only when ``FAIRVID_SMTP_HOST`` is set. Otherwise the letter is
written under ``var/outbox/`` so you can open it and see exactly what the
student would receive.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from ..config import REPO_ROOT


def outbox_dir() -> Path:
    override = os.environ.get("FAIRVID_OUTBOX")
    path = Path(override) if override else REPO_ROOT / "var" / "outbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_letter(event: dict) -> tuple[str, str]:
    """Return ``(subject, body)`` for one finished evaluation."""
    payload = event.get("payload") or {}
    decision = payload.get("decision") or {}
    admit = bool(decision.get("admit"))
    probability = decision.get("probability")
    name = event.get("name") or "applicant"
    application_id = event.get("application_id")
    verdict = "Admitted" if admit else "Not admitted"
    score = f"{round(float(probability) * 100)}%" if probability is not None else "n/a"
    lines = [
        f"Hello {name},",
        "",
        f"Your application {application_id} has been evaluated.",
        "",
        f"Decision: {verdict}",
        f"Admission score: {score}",
        "",
        "Where to improve",
    ]
    improvements = payload.get("improvements") or []
    if improvements:
        lines.extend(f"- {item}" for item in improvements)
    else:
        lines.append(
            "- The interview signals we can still change are already in a strong range. "
            "The decision follows the academic record already on file."
        )
    notes = payload.get("record_notes") or []
    if notes:
        lines.append("")
        lines.append("Already on your record")
        lines.extend(f"- {item}" for item in notes)
    lines.extend([
        "",
        "Suggestions refer only to the interview and the setting. "
        "They do not rewrite grades that are already on file.",
        "",
        "FAIR-VID admissions",
    ])
    subject = f"Your admission decision for {application_id}: {verdict}"
    return subject, "\n".join(lines) + "\n"


def send_letter(event: dict) -> dict:
    """Deliver the letter. Returns a small receipt stored on the notification event."""
    to = event.get("email") or ""
    subject, body = render_letter(event)
    receipt = {"to": to, "subject": subject, "body": body}
    host = os.environ.get("FAIRVID_SMTP_HOST", "").strip()
    if host and to:
        message = EmailMessage()
        message["From"] = os.environ.get("FAIRVID_SMTP_FROM", "admissions@localhost")
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        port = int(os.environ.get("FAIRVID_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if os.environ.get("FAIRVID_SMTP_STARTTLS", "1") != "0":
                smtp.starttls()
            user = os.environ.get("FAIRVID_SMTP_USER")
            password = os.environ.get("FAIRVID_SMTP_PASSWORD")
            if user and password:
                smtp.login(user, password)
            smtp.send_message(message)
        receipt["transport"] = "smtp"
        return receipt

    safe = "".join(ch for ch in event.get("application_id", "letter") if ch.isalnum() or ch in "-_")
    path = outbox_dir() / f"{safe or 'letter'}.txt"
    path.write_text(f"To: {to}\nSubject: {subject}\n\n{body}", encoding="utf-8")
    receipt["transport"] = "outbox"
    receipt["path"] = str(path)
    return receipt
