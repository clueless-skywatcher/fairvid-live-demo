# FAIR-VID live demo

Self-contained web app for the full applicant-scoring flow:

- A **candidate is pre-loaded** (academic record + diploma/transcript already "in
  the system").
- You **record their interview** in the browser, and the app runs the real
  perception pipeline: extract audio → **Whisper** transcript → middle frame →
  **Ollama/Gemma** frame description → **MediaPipe** behaviour metrics →
  transcript grade.
- It then **fuses the documents/record with the live interview** and returns an
  **admission verdict** (admit / do-not-admit + probability) with
  **SHAP / LIME / counterfactual explanations** — so you see *why*, and *what
  would change the decision*.

Everything needed to run it is in this folder. On first start it builds a small
synthetic training cohort and trains the scoring model (~20–40 s, one time); the
candidate is a borderline applicant so the interview visibly swings the verdict.

## Install (once)

```bash
cd ~/Github/fairvid-live-demo
pip install -r requirements.txt
```

## Run

```bash
cd ~/Github/fairvid-live-demo
python3 -m fairvid.webapp
```

Open **http://127.0.0.1:5000** (use `127.0.0.1`/`localhost` — browsers only allow
the camera/mic on a secure origin, and localhost counts). Pick a question, **Start
recording**, then **Stop & analyse**. First run downloads the Whisper and
MediaPipe models.

## Optional: real Ollama/Gemma frame descriptions

Without Ollama the frame-description stage uses a short offline fallback (labelled
`offline` in the UI). For the real model:

```bash
ollama serve &
ollama pull gemma3:4b           # 4b is fast on CPU; 12b is sharper but slow
export FAIRVID_VLM_MODEL=gemma3:4b
python3 -m fairvid.webapp
```

The UI badge then shows `ollama gemma3:4b`.

## Layout

```
fairvid/
├── config.py                 # paths, study programs, the VLM model name
├── datagen/                  # questions loader + answer word-lists the grader uses
├── pipeline/
│   ├── vlm.py                # Ollama/Gemma frame description (offline fallback)
│   ├── behaviour_video.py    # MediaPipe behaviour analysis (ported from the notebook)
│   └── grader.py             # offline transcript-auditor grade
└── webapp/
    ├── app.py                # Flask app + record UI
    └── process_video.py      # runs the stages on one recording
```
