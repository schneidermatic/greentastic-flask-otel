#!/bin/sh
# Start-up of the app container (see Dockerfile).
set -e

# 1. create tables, demo products and demo users (waits for PostgreSQL)
# 2. load the products into Elasticsearch - in the background, Elasticsearch needs about a minute to start
# Both run without OpenTelemetry (empty endpoint): they are one-off tasks, not part of the shop.
OTEL_EXPORTER_OTLP_ENDPOINT= flask --app greentastic init-db
OTEL_EXPORTER_OTLP_ENDPOINT= flask --app greentastic reindex &

# 3. serve the shop on port 8000 (settings in gunicorn.conf.py); every worker sets up OpenTelemetry itself
exec gunicorn -c gunicorn.conf.py "greentastic:create_app()"
