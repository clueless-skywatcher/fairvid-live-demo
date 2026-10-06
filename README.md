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
ollama pull gemma3:1b
ollama pull moondream
export FAIRVID_GRADER_MODEL=gemma3:1b
export FAIRVID_VLM_MODEL=moondream
python3 -m fairvid.webapp
```

The grade line then shows `ollama · gemma3:1b`, and the frame badge shows `ollama moondream`.

## Event-driven admissions flow

Each step is a Kafka consumer. The progress manager answers
"how far is this application?" and, after scoring, the student is emailed the
decision and what to improve. Diagrams and the topic table are in
[docs/architecture.md](docs/architecture.md).

```bash
export FAIRVID_KAFKA_BOOTSTRAP=localhost:9092
python -m fairvid.events                 # list consumers and topics
python -m fairvid.events.manager         # http://127.0.0.1:5001
python -m fairvid.events.consumers.intake
# start the other consumers the same way; see the architecture page
```

Without a broker, one case runs in-process and the letter lands in `var/outbox/`:

```bash
python -m fairvid.events.local
```

The full agent map, with sequence and class diagrams, is in
[docs/architecture.md](docs/architecture.md).

## Run with Docker

You need Docker with the Compose plugin (`docker compose`, not the old
`docker-compose`). The image installs `requirements.txt`, the `fairvid` package,
and the synthetic cohort in `data/`. Notebooks, tests, and docs are left out.

### Web demo only

```bash
docker build -t fairvid:local .
docker run --rm -p 5000:5000 fairvid:local
```

Open **http://127.0.0.1:5000**. The camera works because the browser still sees
`localhost`. The Whisper and MediaPipe models download on the first recording,
and again whenever you start a new container. This container is the web demo
only. It does not listen on port 5001.

To use Ollama running on your own machine, pull the small models on the host,
then pass their names into the container. The image does not contain them.

```bash
ollama pull gemma3:1b
ollama pull moondream
docker run --rm -p 5000:5000 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e FAIRVID_GRADER_MODEL=gemma3:1b \
  -e FAIRVID_VLM_MODEL=moondream \
  fairvid:local
```

`gemma3:1b` grades the transcript. `moondream` describes the video frame.
`moondream` cannot grade text: a text-only prompt comes back empty. Whisper
stays inside the container as the `base` model. Leave the Ollama server you
already have running. Do not publish port 5001 here. That port belongs to the
progress manager in the next section.

### Kafka broker, every consumer, and the manager

`docker-compose.yml` starts one Kafka broker, the 14 consumers, and the progress
manager. The consumers wait until the broker passes its health check.

```bash
docker compose up --build -d
docker compose ps                     # every service should be "running"
docker compose logs -f evaluate notify
```

| From your machine | Address |
| --- | --- |
| Progress manager | http://127.0.0.1:5001 |
| Kafka broker | `localhost:9092` |

Submit an application through the manager. It publishes
`admissions.application.received`, and the consumers take it from there:

```bash
curl -X POST http://127.0.0.1:5001/applications \
  -H 'Content-Type: application/json' \
  -d '{
        "application_id": "demo-1001",
        "email": "ada@example.com",
        "name": "Ada Applicant",
        "gpa": 2.8,
        "test_score": 64,
        "english_score": 6.0,
        "work_experience_years": 0,
        "question": "Why this programme?",
        "transcript": "I think the programme is good and important."
      }'
```

Ask how far it has got:

```bash
curl http://127.0.0.1:5001/applications/demo-1001
```

`"overall": "complete"` means the decision letter has been written. Without
mail settings it is saved in the shared volume:

```bash
docker compose exec manager cat /app/var/outbox/demo-1001.txt
```

To send real email, add these under `environment:` in the `x-fairvid` block of
`docker-compose.yml`: `FAIRVID_SMTP_HOST`, `FAIRVID_SMTP_PORT`,
`FAIRVID_SMTP_USER`, `FAIRVID_SMTP_PASSWORD`, `FAIRVID_SMTP_FROM`.

The example sends a transcript in the request, so no video is needed. Video,
audio, and frame paths in a request are read inside the containers, and nothing
on your machine is mounted. If you leave them out, those stages still complete,
with empty results and neutral values for scoring.

Progress files, join state, and letters live in the `fairvid-state` volume.

```bash
docker compose down        # stop, keep the volume
docker compose down -v     # stop and delete progress and letters
```

## Layout

```
Dockerfile                    # one image for the web demo, consumers, and manager
docker-compose.yml            # Kafka broker + all consumers + the manager
fairvid/
├── config.py                 # paths, study programs, the VLM model name
├── datagen/                  # questions loader + answer word-lists the grader uses
├── events/
│   ├── topics.py             # Kafka topic names and the stage list
│   ├── consumers/            # one script per admissions step
│   ├── manager.py            # progress API on port 5001
│   └── local.py              # one case in-process, no broker
├── pipeline/
│   ├── vlm.py                # Ollama/Gemma frame description (offline fallback)
│   ├── behaviour_video.py    # MediaPipe behaviour analysis (ported from the notebook)
│   └── grader.py             # offline transcript-auditor grade
└── webapp/
    ├── app.py                # Flask app + record UI
    └── process_video.py      # runs the stages on one recording
```
