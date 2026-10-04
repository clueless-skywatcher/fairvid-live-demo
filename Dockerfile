# FAIR-VID. Default process is the live demo on port 5000.
# The same image can run the progress manager or one Kafka consumer:
#   docker run --rm -p 5001:5001 -e FAIRVID_KAFKA_BOOTSTRAP=host.docker.internal:9092 IMAGE python -m fairvid.events.manager
#   docker run --rm -e FAIRVID_KAFKA_BOOTSTRAP=host.docker.internal:9092 IMAGE python -m fairvid.events.consumers.intake
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FAIRVID_HOST=0.0.0.0 \
    FAIRVID_PORT=5000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fairvid ./fairvid
COPY data ./data

RUN useradd --create-home --uid 1000 fairvid \
    && mkdir -p /app/var /tmp/fairvid_runs \
    && chown -R fairvid:fairvid /app /tmp/fairvid_runs
USER fairvid

EXPOSE 5000

CMD ["python", "-m", "fairvid.webapp"]
