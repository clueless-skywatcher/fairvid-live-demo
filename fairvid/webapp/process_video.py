"""Run the real perception pipeline on one recorded interview video.

Given a webm/mp4 the user recorded in the browser, this runs the same stages as
the Colab notebooks and returns their outputs:

  1. ffmpeg   -> extract 16 kHz mono WAV (for ASR) and an MP4 (for OpenCV)
  2. Whisper  -> transcript           (faster-whisper, "base")
  3. OpenCV   -> middle frame JPEG
  4. Ollama   -> frame description     (Gemma-3, with offline fallback)
  5. MediaPipe-> behaviour metrics
  6. grader   -> transcript grade JSON (offline auditor stand-in)

Every stage is wrapped: if a tool is missing it records an error and the rest
continue, so the demo never hard-crashes.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

_WHISPER = None  # cached model


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd) -> bool:
    return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def extract_audio(src: Path, wav: Path) -> bool:
    return _run([_ffmpeg(), "-y", "-i", str(src), "-vn", "-ar", "16000", "-ac", "1", str(wav)])


def to_mp4(src: Path, mp4: Path) -> Path:
    """Transcode to H.264 MP4 for reliable OpenCV reading; fall back to source."""
    if _run([_ffmpeg(), "-y", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-an", str(mp4)]):
        return mp4
    return src


def middle_frame(video: Path, jpg: Path) -> bool:
    import cv2
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 2))
    ok, frame = cap.read()
    if not ok:  # fallback: first readable frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = cap.read()
    cap.release()
    if ok:
        cv2.imwrite(str(jpg), frame)
    return ok


def transcribe(wav: Path) -> str:
    global _WHISPER
    from faster_whisper import WhisperModel
    if _WHISPER is None:
        _WHISPER = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = _WHISPER.transcribe(str(wav))
    return " ".join(s.text.strip() for s in segments).strip()


def process(video_path: str, question: str, workdir: str) -> dict:
    """Run all stages; return a results dict with per-stage status."""
    from ..pipeline import vlm
    from ..pipeline.grader import grade_transcript

    src = Path(video_path)
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    wav, mp4, jpg = work / "audio.wav", work / "video.mp4", work / "frame.jpg"
    out: dict = {"question": question, "stages": {}}

    def stage(name, fn):
        t0 = time.time()
        try:
            res = fn()
            out["stages"][name] = {"ok": True, "secs": round(time.time() - t0, 1)}
            return res
        except Exception as e:
            out["stages"][name] = {"ok": False, "secs": round(time.time() - t0, 1),
                                    "error": f"{type(e).__name__}: {e}"}
            return None

    video_for_cv = stage("convert", lambda: to_mp4(src, mp4)) or src
    stage("audio", lambda: extract_audio(src, wav))
    out["transcript"] = stage("transcribe", lambda: transcribe(wav)) if wav.exists() else None
    got_frame = stage("frame", lambda: middle_frame(video_for_cv, jpg))
    if got_frame and jpg.exists():
        out["frame_file"] = str(jpg)
        out["frame_description"] = stage("vlm_describe", lambda: vlm.describe_image(jpg))
    out["behaviour"] = stage("behaviour", lambda: _behaviour(video_for_cv))
    if out.get("transcript"):
        out["grade"] = stage("grade", lambda: grade_transcript(question, out["transcript"]))
    return out


def _behaviour(video: Path) -> dict:
    from ..pipeline.behaviour_video import analyse_video
    return analyse_video(str(video))
