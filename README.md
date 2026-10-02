# Greentastic

A small web shop for fruits, vegetables, homemade and handcrafted products. It is deliberately simple and is
meant as an **example application for OpenTelemetry**: one Python web app that talks to a database, a cache and a
search engine, so every request produces an interesting trace.

```
                         ┌──────────────────────────────┐   OTLP (traces, metrics, logs)
  Browser  ──HTTP──►     │  app  (Flask shop, gunicorn) │ ─────────────────────────────►  edot-collector
                         └──┬────────────┬───────────┬──┘                                   │   │ scrapes postgres,
                            │ SQL        │ GET/SET   │ search (HTTPS)                       │   │ redis, containers
                            ▼            ▼           ▼                                      ▼   │
                        postgres       redis        es01  ◄─────────────────────────────────────┘
                       (all data)     (cache)   (product search + telemetry)  ◄──  kibana (UI)
```

[`docker-compose.yml`](docker-compose.yml) uses the same configuration as the MiniELK recipe *"Run the ELK Stack
with OTEL"*: a `setup` container creates the TLS certificates, `es01` runs with security enabled, `kibana`,
`edot-collector`, `postgres` and `redis` keep their names, all on the Docker network `elastic`. Only the `app`
service is the shop (plus `locust` for load tests, only started on demand). That makes it easy to merge both projects.

## Quick start

```bash
source .xrc      # load the x_ shortcuts
x_up             # build, start and check everything (~3-5 min the first time)
x_locust_run     # load test with Locust against the REST API (20 users, 2 minutes)
```

* Shop: http://localhost:8000 - logins `user` / `user` (customer), `seller` / `seller`, `admin` / `admin`
* Kibana: https://localhost:5601 - user `elastic`, password `changeme` (self-signed certificate: accept it in the browser)

`x_ls` lists all shortcuts, `x_otel_status` counts the received telemetry, `x_down` stops everything and deletes
all data. Needs about 5 GB of free memory (Elasticsearch, Kibana, collector).

## What happens on a request

| User action | Route | What the app does |
|---|---|---|
| Open a category | `GET /category/fruits` | ask **Redis** for `products:fruits`; on a miss read **PostgreSQL** and store the result in Redis for 60 s |
| Search | `GET /search?q=appel` | full-text query to **Elasticsearch** (typo tolerant) |
| Type in the search box | `GET /api/suggest?q=ap` | type-ahead query to **Elasticsearch**, called by `static/js/search.js` |
| Log in | `POST /login` | read the user from **PostgreSQL**, check the password hash |
| Change password | `POST /profile` | check the current password, store the new hash in **PostgreSQL** |
| Add to cart | `POST /cart/add` | insert into `cart_items` (**PostgreSQL**) |
| Checkout | `POST /checkout` | one **PostgreSQL** transaction: create an `orders` row, copy the cart into `order_items`, empty the cart |
| View / change an order | `GET` / `POST /orders/<id>` | read or update the order and its items in **PostgreSQL** (only while the status is `new`) |
| Delete an order | `POST /orders/<id>/delete` | delete the order, its items go with it (`ON DELETE CASCADE`) |
| Add / delete product (seller) | `POST /manage/products/...` | write **PostgreSQL**, delete the **Redis** key, update **Elasticsearch** |

If Redis or Elasticsearch is down, the shop keeps working: without cache, or with a "search unavailable" notice.
Stopping Redis (`docker compose stop redis`, later `start`) is a good way to see errors in your telemetry: warning
logs, `cache.result=error` spans and failed Redis calls in the traces.

## REST API

Everything the web pages can do is also available as JSON under `/api` ([`greentastic/api.py`](greentastic/api.py)).
Web pages and API call the same functions (`products.py`, `orders.py`, `accounts.py`, `search.py`), so both
produce the same traces, metrics and logs. Log in with `POST /api/login` and send the session cookie with every
further request; errors come back as `{"error": "..."}`.

| Method | Path | Body (JSON) | Who |
|---|---|---|---|
| GET | `/api/categories` | | everyone |
| GET | `/api/products`, `/api/products?category=fruits`, `/api/products/<id>` | | everyone |
| GET | `/api/search?q=appel`, `/api/suggest?q=ap` | | everyone |
| POST | `/api/register` | `username`, `password`, `email` | everyone |
| POST | `/api/login`, `/api/logout` | `username`, `password` | everyone |
| GET / PUT | `/api/profile` | `email` | logged in |
| PUT | `/api/profile/password` | `current_password`, `new_password` | logged in |
| GET / POST | `/api/cart` | `product_id`, `quantity` | logged in |
| POST | `/api/checkout` | `name`, `street`, `city`, `payment` | logged in |
| GET | `/api/orders`, `/api/orders/<id>` | | logged in (own orders) |
| PUT | `/api/orders/<id>` | `name`, `street`, `city`, `payment`, `quantities` `{"<item id>": n}` | logged in, status `new` |
| DELETE | `/api/orders/<id>` | | logged in, status `new` |
| POST / DELETE | `/api/products`, `/api/products/<id>` | `category`, `name`, `description`, `price`, `stock`, `unit`, `image` | seller, admin |
| GET | `/api/manage/orders` | | seller, admin |
| GET / DELETE | `/api/users`, `/api/users/<id>` | | admin |

```bash
curl -c jar -H 'Content-Type: application/json' -d '{"username":"user","password":"user"}' localhost:8000/api/login
curl -b jar -H 'Content-Type: application/json' -d '{"product_id":1,"quantity":2}' localhost:8000/api/cart
curl -b jar -H 'Content-Type: application/json' -d '{"name":"Ann","street":"Main 1","city":"Town","payment":"cash on delivery"}' localhost:8000/api/checkout
```

### Simulated errors

[`greentastic/simulate.py`](greentastic/simulate.py) has endpoints that fail or are slow on purpose, to see what
problems look like in the telemetry (`GET /api/simulate/` lists them):

| Path | What happens | Status | In the trace |
|---|---|---|---|
| `/api/simulate/error` | exception, caught and recorded | 500 | span `failing step` with status ERROR and the exception |
| `/api/simulate/crash` | unhandled exception (`ZeroDivisionError`) | 500 | server span ERROR, traceback in the logs |
| `/api/simulate/slow?seconds=2` | `SELECT pg_sleep(...)` | 200 | one long SQL span (max. 10 s) |
| `/api/simulate/db-error` | query on a table that does not exist | 500 | SQL span ERROR (`UndefinedTable`) |
| `/api/simulate/search-error` | invalid query, rejected by Elasticsearch | 502 | Elasticsearch span ERROR (400 Bad Request) |
| `/api/simulate/timeout?seconds=2` | external payment provider does not answer (simulated) | 504 | client span `POST payment-provider` ERROR |
| `/api/simulate/random` | one of the above | | |

Every call also counts in the metric `greentastic.simulated_errors` (attribute `kind`) and writes a log record.

## Load test with Locust

[`loadtest/locustfile.py`](loadtest/locustfile.py) simulates three kinds of users against the REST API:

| User | Weight | What it does |
|---|---|---|
| `Visitor` | 3 | anonymous: categories (Redis), product details, searches with typos and the type-ahead (Elasticsearch), a 404 and a wrong password now and then |
| `Customer` | 2 | registers its own account, fills the cart, checks out, looks at, changes and deletes orders, edits the profile |
| `Seller` | 1 | watches all orders, adds products and deletes them again (PostgreSQL + Redis + Elasticsearch) |
| `Trouble` | 1 | calls the [simulated errors](#simulated-errors); the expected error codes count as success in Locust |

Locust runs as the container `locust` (compose profile `loadtest`, not started by `x_up`):

* `x_locust` - web UI on http://localhost:8089: choose the number of users, start, watch requests/s and response times
* `x_locust_run [users=20] [spawn rate=5] [duration=2m]` - headless run, prints the summary
* `x_locust_stop`

Without Docker: `pip install locust && locust -f loadtest/locustfile.py --host http://localhost:8000`.
The quick shell alternative `x_load [count]` uses curl on the web pages.

## OpenTelemetry

Everything is in [`greentastic/telemetry.py`](greentastic/telemetry.py) and only active when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set (in `docker-compose.yml`), so tests and local runs need no collector.

| Signal | Where it comes from |
|---|---|
| **Traces** | automatic instrumentation: a server span per HTTP request (Flask) and a client span for every SQL statement (psycopg), Redis command and Elasticsearch request. Own spans: `cache get_or_load` (attribute `cache.result` = hit/miss/error) and `place order` (`order.id`, `order.items`, `order.value`) |
| **Metrics** | HTTP server metrics (Flask) and the shop's own counters: `greentastic.orders.placed`, `greentastic.orders.value` (EUR), `greentastic.cart.additions`, `greentastic.cache.lookups`, `greentastic.searches`, `greentastic.logins`, `greentastic.simulated_errors` |
| **Logs** | every Python log record (logins, orders, cache/search problems), with the trace id of the request |

The resource says who is sending: `service.name=greentastic` (`OTEL_SERVICE_NAME`), `service.version`,
`deployment.environment=demo`, one `service.instance.id` per gunicorn worker, plus `host.name` and `container.id`.

Two details that are easy to get wrong:

* gunicorn must **not** preload the app ([`gunicorn.conf.py`](gunicorn.conf.py)): the SDK starts exporter threads,
  which do not survive the fork into the workers. `create_app()` - and with it `telemetry.setup()` - runs in each worker.
* `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`: Elasticsearch drops cumulative histograms.

The **EDOT Collector** ([`otel-collector.yml`](otel-collector.yml), Elastic Agent in OpenTelemetry mode, same
configuration as in the MiniELK recipe) receives OTLP on port 4317, scrapes PostgreSQL, Redis and the Docker
container metrics, derives the APM aggregations from the traces and writes everything to `es01` in
OpenTelemetry format.

### Looking at the telemetry

Log into Kibana (https://localhost:5601, `elastic` / `changeme`) after `x_load`:

* **Observability → Applications → Service inventory → greentastic**: latency, throughput, failed transactions;
  open a transaction (e.g. `POST /checkout`) to see its trace with all SQL statements.
* **Dependencies** tab / **Service map**: `postgres:5432`, `redis:6379` and `es01:9200`.
* **Discover**: data views `traces-*.otel-*`, `metrics-*.otel-*`, `logs-*.otel-*`; filter e.g. on
  `service.name : greentastic and severity_text : WARN`, or chart `greentastic.orders.value`.
* **Infrastructure**: the containers (`docker_stats`), PostgreSQL and Redis metrics.

## Code map

```
greentastic/
  __init__.py   create_app(): configuration from environment variables, registers the three blueprints
  shop.py       web pages for customers: home, category, search, cart, checkout, orders
  auth.py       web pages for login, registration, profile, logout; @login_required(role)
  manage.py     web pages of the back office (/manage): products and orders for sellers, users for admins
  api.py        the REST API (/api/...): the same functions as JSON
  simulate.py   /api/simulate/...: errors and slow requests on purpose
  products.py   the catalogue: keeps PostgreSQL, Redis and Elasticsearch in sync
  orders.py     cart, checkout and orders
  accounts.py   users: login check, registration, email, password
  db.py         PostgreSQL: query(), query_one(), execute()
  cache.py      Redis: get_or_load(), delete()
  search.py     Elasticsearch: find(), suggest(), add(), remove(), reindex()
  telemetry.py  OpenTelemetry: SDK set-up, automatic instrumentation, the shop's own metrics
  cli.py        `flask --app greentastic init-db` and `reindex`, run when the container starts
  sql/          schema.sql (5 tables) and demo_products.sql
  templates/    one Jinja template per page, base.html (layout) and macros.html
  static/       images (see static/CREDITS.md), Bootstrap (vendored, works offline), search.js
tests/          pytest, with fake Redis/Elasticsearch - no running service needed (x_test)
loadtest/       locustfile.py - load test against the REST API (x_locust, x_locust_run)
start.sh        start-up of the app container (init-db, reindex, gunicorn)
gunicorn.conf.py, Dockerfile, docker-compose.yml, otel-collector.yml, .env (demo settings), .xrc (x_ shortcuts)
```

Database tables: `users` (with a `role`: customer, seller, admin), `products`, `cart_items`, `orders` and `order_items`.

## Start-up sequence

`docker compose up` runs `setup` (certificates, `kibana_system` password), then `es01`, `postgres` and `redis`;
`kibana` and `edot-collector` follow once `es01` is healthy. The `app` container waits for `es01`, the collector,
PostgreSQL and Redis, then runs [`start.sh`](start.sh):

1. `flask --app greentastic init-db` - create tables, demo products and demo users (existing data is kept)
2. `flask --app greentastic reindex &` - load all products into Elasticsearch (index `greentastic-products`)
3. `gunicorn` - serve the app on port 8000

The two setup tasks run without telemetry; only the shop itself (the gunicorn workers) sends data.

## Configuration

Everything is set through environment variables in `docker-compose.yml`; the demo values are in `.env`
(same variables as in the MiniELK recipe, plus the shop's own).

| Variable | Used for |
|---|---|
| `DATABASE_URL`, `REDIS_URL`, `ELASTICSEARCH_URL` | where the services are (set by `docker-compose.yml`) |
| `ELASTIC_PASSWORD`, `ELASTICSEARCH_CA_CERTS` | the shop's search logs into `es01` as `elastic` over HTTPS with the cluster's CA |
| `SECRET_KEY` | Flask session cookie |
| `CUSTOMER_*`, `SELLER_*`, `ADMIN_*` | demo accounts created by `init-db` |
| `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`, `OTEL_EXPORTER_OTLP_*` | OpenTelemetry (standard SDK variables) |
| `APP_PORT`, `KIBANA_PORT`, `ES_PORT`, `OTLP_GRPC_PORT`, `OTLP_HTTP_PORT`, `LOCUST_PORT` | ports on your machine |
| `ELASTIC_PASSWORD`, `KIBANA_PASSWORD`, `STACK_VERSION`, `ES_MEM_LIMIT`, `KB_MEM_LIMIT`, ... | Elastic Stack, as in the MiniELK recipe |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | the shop's database |

## Credits

Photos: Wikimedia Commons, see [`greentastic/static/CREDITS.md`](greentastic/static/CREDITS.md).
Originally a college project from 2021.
