# CHANGES

0.1.0 (2026-10-02)
---------------------
### Greentastic web shop (rewrite of the 2021 college project 'Sellyard')
* Added   - 'greentastic/': Flask application factory ('create_app()') with the blueprints 'shop', 'auth', 'manage' (web pages), 'api' (REST/JSON) and 'simulate'; the logic lives in 'products.py', 'orders.py', 'accounts.py' and 'search.py' and is shared by web pages and API.
* Added   - 'greentastic/sql/schema.sql', 'demo_products.sql': PostgreSQL schema with 5 tables ('users' with a 'role', 'products', 'cart_items', 'orders', 'order_items') and 29 demo products in 4 categories; prices in euro.
* Added   - 'greentastic/cli.py': 'flask --app greentastic init-db' (tables, demo data, demo accounts customer/seller/admin) and 'reindex' (Elasticsearch product index).
* Added   - Customer functions: browse categories, full-text search with typo tolerance and type-ahead suggestions (Elasticsearch), cart, fake checkout, order history with detail view, changing and deleting orders while their status is 'new', profile page (email, password).
* Added   - Back office ('/manage'): sellers and admins manage products and see all orders, admins manage users.
* Added   - 'greentastic/cache.py': Redis cache for the product lists, invalidated on product changes; the shop keeps working without Redis.
* Added   - 'greentastic/templates/': Bootstrap 5 design (navbar with search and suggestions, four-column footer); Bootstrap and Bootstrap Icons vendored in 'static/vendor/' so the shop works air-gapped.
* Added   - 'greentastic/static/': free photos from Wikimedia Commons (CC0, public domain, CC BY, CC BY-SA), listed with source, author and license in 'static/CREDITS.md'.
* Removed - 'main.py', the four product tables per category, the separate user/seller/admin tables, 'mysql.connector' and all photos with unclear or commercial (iStock, Getty, Shutterstock) licenses.

### REST API, simulated errors and load test
* Added   - 'greentastic/api.py': JSON endpoints under '/api' for everything the web pages can do (catalogue, search, register/login, profile, cart, checkout, orders, products, users); errors as '{"error": ...}'.
* Added   - 'greentastic/simulate.py': '/api/simulate/*' endpoints that fail on purpose - handled and unhandled exceptions, slow SQL ('pg_sleep'), SQL error, Elasticsearch error, payment provider timeout.
* Added   - 'loadtest/locustfile.py': Locust load test with the users 'Visitor', 'Customer' (own account, orders), 'Seller' (adds/deletes products) and 'Trouble' (simulated errors); compose service 'locust' (profile 'loadtest').

### OpenTelemetry
* Added   - 'greentastic/telemetry.py': OpenTelemetry SDK (traces, metrics, logs via OTLP/gRPC), automatic instrumentation of Flask, psycopg, Redis and Elasticsearch, own spans ('cache get_or_load', 'place order') and metrics ('greentastic.orders.placed', '.orders.value', '.cart.additions', '.cache.lookups', '.searches', '.logins', '.simulated_errors'); resource with 'service.instance.id' per gunicorn worker, 'host.name' and 'container.id'.
* Added   - 'gunicorn.conf.py': 2 workers without 'preload_app', so the exporter threads are started in every worker.
* Added   - 'docker-compose.yml', 'otel-collector.yml', '.env': same configuration as 'MiniELK-HOWTOs/HowTo - Run the ELK Stack with OTEL' ('setup', 'es01' with security/TLS, 'kibana', 'edot-collector', 'postgres', 'redis', network 'elastic'); 'es01' holds the product index and the telemetry.

### Tooling and documentation
* Added   - 'Dockerfile', 'start.sh': image 'greentastic:latest'; start-up runs 'init-db', 'reindex' (in the background) and gunicorn.
* Added   - 'pyproject.toml': package 'greentastic' with its dependencies, extra 'dev' (pytest).
* Added   - '.xrc': 'x_' shortcuts - 'x_up' (start and check every service), 'x_down' (delete all data incl. leftover volumes), 'x_status', 'x_otel_status', 'x_load', 'x_locust', 'x_locust_run', 'x_psql', 'x_redis', 'x_es', 'x_logs', 'x_test' and more.
* Added   - 'tests/': pytest suite with fake Redis and Elasticsearch clients (no running service needed).
* Added   - 'README.md': architecture, request flows, REST API, simulated errors, load test, OpenTelemetry and where to find the data in Kibana; 'CLAUDE.md' for Claude Code.
* Added   - '.gitignore', '.dockerignore'.
