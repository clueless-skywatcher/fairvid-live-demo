"""Kafka topic names for the admissions flow.

One topic per step. A consumer reads only its own topic and publishes the next
one. The progress manager listens to ``PROGRESS`` rather than to every step.
"""

# Intake. The manager (or a submit command) publishes this. The intake consumer
# fans it out onto the document track and the interview track.
APPLICATION_RECEIVED = "admissions.application.received"

# Document track, in order. Summary completion fans out to reconcile and eligibility.
DOCUMENTS_UPLOADED = "admissions.documents.uploaded"
DOCUMENTS_OCR_COMPLETED = "admissions.documents.ocr.completed"
DOCUMENTS_PAGES_MERGED = "admissions.documents.pages.merged"
DOCUMENTS_SUMMARY_COMPLETED = "admissions.documents.summary.completed"
DOCUMENTS_RECONCILED = "admissions.documents.reconciled"
DOCUMENTS_ELIGIBILITY_COMPLETED = "admissions.documents.eligibility.completed"

# Interview track. Recording fans out to audio, behaviour, and the frame agent.
# Audio then fans out to transcription and prosody.
INTERVIEW_RECORDED = "admissions.interview.recorded"
INTERVIEW_AUDIO_EXTRACTED = "admissions.interview.audio.extracted"
INTERVIEW_TRANSCRIPT_COMPLETED = "admissions.interview.transcript.completed"
INTERVIEW_GRADE_COMPLETED = "admissions.interview.grade.completed"
INTERVIEW_PROSODY_COMPLETED = "admissions.interview.prosody.completed"
INTERVIEW_BEHAVIOUR_COMPLETED = "admissions.interview.behaviour.completed"
INTERVIEW_FRAME_COMPLETED = "admissions.interview.frame.completed"

# Decision and the letter to the student.
EVALUATION_COMPLETED = "admissions.evaluation.completed"
NOTIFICATION_SENT = "admissions.notification.sent"

# Side channel. Every consumer publishes a copy here so the manager can
# update its case file without subscribing to the whole pipeline.
PROGRESS = "admissions.progress"

# Request/reply. Ask the manager how far one application has got.
MANAGER_REQUEST = "admissions.manager.request"
MANAGER_RESPONSE = "admissions.manager.response"

# Stages the manager shows, in display order. Reconciliation is recorded but
# does not block the decision: eligibility reads the summary, not the vote.
STAGE_ORDER = (
    "application.received",
    "documents.ocr",
    "documents.pages",
    "documents.summary",
    "documents.reconcile",
    "documents.eligibility",
    "interview.audio",
    "interview.transcript",
    "interview.grade",
    "interview.prosody",
    "interview.behaviour",
    "interview.frame",
    "evaluation",
    "notification",
)

# The evaluation consumer waits for these stages. All of them must be completed.
JOIN_STAGES = (
    "documents.eligibility",
    "interview.grade",
    "interview.prosody",
    "interview.behaviour",
    "interview.frame",
)
