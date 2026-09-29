# FAIR-VID live demo web app

Records **your** webcam interview in the browser and runs the real pipeline on it:
extract audio → **Whisper** transcript → middle frame → **Ollama/Gemma** frame
description → **MediaPipe** behaviour → transcript grade. Then it shows every
stage's output on one page.

## Run

```bash
cd thesis-colab
python -m fairvid.webapp
```

Open **http://127.0.0.1:5000** in Chrome/Edge. Use `127.0.0.1` (or `localhost`) —
browsers only allow camera/mic on a secure origin, and localhost counts. Allow
the camera/mic prompt, pick a question, **Start recording**, then **Stop &
analyse**. Processing takes ~20–40 s on CPU (Whisper + MediaPipe).

## Ollama (real frame descriptions)

Without Ollama the frame-description stage uses a short offline fallback (clearly
labelled in the UI). For the real Gemma description, before the demo:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull gemma3:4b           # 4b is fast on CPU; 12b is sharper but slow
export FAIRVID_VLM_MODEL=gemma3:4b
python -m fairvid.webapp
```

The UI shows a badge for which backend answered (`ollama gemma3:4b` vs `offline`).

## What's already prepared

- ffmpeg ships via `imageio-ffmpeg` (no system install needed).
- The Whisper "base" model is downloaded/warmed.
- The MediaPipe face-landmarker model downloads once to `/tmp` on first use.
- Recordings and outputs are written under `/tmp/fairvid_runs/<id>/`.

## Stages and where they live

| Stage | Code | Tool |
| --- | --- | --- |
| audio + transcript | `process_video.py` | ffmpeg + faster-whisper |
| middle frame | `process_video.py` | OpenCV |
| frame description | `pipeline/vlm.py` | Ollama/Gemma (offline fallback) |
| behaviour metrics | `pipeline/behaviour_video.py` | MediaPipe (ported from the notebook) |
| transcript grade | `pipeline/grader.py` | offline auditor stand-in |

Every stage is wrapped: if a tool is missing the UI marks it "skipped" and the
rest still run, so the demo never hard-crashes.
