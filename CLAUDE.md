# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Greentastic is a demo web shop (Flask + PostgreSQL + Redis + Elasticsearch) meant as an **OpenTelemetry example**.
Keep the code simple and easy to follow - readability beats features. `README.md` explains the architecture,
request flows and code map; keep it in sync when routes, modules or services change.

## Commands

`source .xrc`, then:

- `x_up` - build and start all containers, then `x_check` (app, postgres, redis, es01, search index, collector, Kibana)
- `x_locust` (web UI :8089) / `x_locust_run [users] [spawn] [time]` load-test the REST API with `loadtest/locustfile.py`
  (compose service `locust`, profile `loadtest`); `x_load [n] [pause]` is a quick curl-based alternative; `x_otel_status` counts telemetry docs per OTel data stream
- `x_stop` keeps data, `x_down` deletes the volumes (needed after changing `sql/schema.sql`)
- `x_logs [service]`, `x_ps`, `x_psql`, `x_redis`, `x_es`, `x_status`, `x_load` (traffic generator)
- `x_test` runs pytest inside the app container; locally: `pip install -e ".[dev]" && pytest`
- Single test: `pytest tests/test_search.py::test_suggest`

## Architecture notes

- `create_app()` in `greentastic/__init__.py`; blueprints `shop`, `auth`, `manage` (`/manage`) render HTML, `api`
  (`/api`) returns JSON. All four are thin: the logic (and the telemetry) lives in `products.py`, `orders.py`,
  `accounts.py`, `search.py` - add new behaviour there and expose it in both a page and the API.
  `login_required` answers 401 JSON for the `api` blueprint; `api.json_error` turns aborts into `{"error": ...}`.
- `simulate.py` (`/api/simulate/*`) fails on purpose (exceptions, slow SQL, SQL/Elasticsearch errors, payment
  timeout) for the telemetry demo; the Locust user `Trouble` calls it. Keep it separate from the real shop logic. `CATEGORIES` there
  maps category key (= image folder in `static/`) to label and card image.
- Rows are dicts (`psycopg` `dict_row`); templates use `p.name`, `o.price`.
- `products.py` is the only place that writes products: it updates PostgreSQL, deletes the Redis key
  `products:<category>` and updates the Elasticsearch index `greentastic-products`.
- Redis and Elasticsearch are optional at runtime: `cache.py` falls back to the loader, `search.py` raises
  `SearchUnavailable` (search page shows a notice, suggestions return `[]`). Tests replace the clients via
  `app.extensions["redis"]` / `app.extensions["elasticsearch"]` (see `tests/conftest.py`).
- Cached rows are JSON, so prices from Redis are strings; the `euro` template filter handles both.
- Roles live in `users.role`; `@login_required("seller", "admin")` protects views.
- Container start (`start.sh`): `init-db` -> `reindex` in the background -> gunicorn (`gunicorn.conf.py`, no
  preload!) `greentastic:create_app()`. The two CLI tasks run with an empty `OTEL_EXPORTER_OTLP_ENDPOINT`.
  Published: app, Kibana, es01, OTLP ports (as in the MiniELK recipe).
- OpenTelemetry lives in `telemetry.py`: `setup(app)` (called at the end of `create_app`) is a no-op without
  `OTEL_EXPORTER_OTLP_ENDPOINT`. Own instruments (`tracer`, counters/histograms) are module-level and usable
  everywhere; keep metric names `greentastic.*` and attribute values low-cardinality.
- `docker-compose.yml`, `otel-collector.yml` and `.env` deliberately mirror
  `~/workspace-01/Elastic/MiniELK-HOWTOs/HowTo - Run the ELK Stack with OTEL` (service names `setup`, `es01`,
  `kibana`, `edot-collector`, `postgres`, `redis`, network `elastic`) so the projects can be merged; only the
  `app` service differs (plus the optional `locust` service, profile `loadtest`). Keep it that way.
- `es01` has security + TLS: the shop's search client uses `ELASTIC_PASSWORD` and the CA from the `certs` volume
  (`ELASTICSEARCH_CA_CERTS=/certs/ca/ca.crt`). The same cluster holds the product index and the telemetry.
- Every image in `static/` must be listed in `static/CREDITS.md` (CC0/public domain/CC BY/CC BY-SA only).
- Bootstrap and Bootstrap Icons are vendored in `static/vendor/` (works offline) - no CDNs.
