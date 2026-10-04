"""Event-driven admissions flow.

Each step has a Kafka topic and a consumer script under ``consumers/``.
The progress manager answers "how far is this application?" over HTTP and
over ``admissions.manager.request``.
"""
