"""Greentastic - a small web shop used as an example application.

    Browser -> Flask (gunicorn) -> PostgreSQL     users, products, cart, orders   (db.py)
                                -> Redis          cached product lists          (cache.py)
                                -> Elasticsearch  product search                (search.py)
            and sends traces, metrics and logs via OTLP to the EDOT collector (telemetry.py),
            which stores them in the same Elasticsearch; Kibana shows them

Every setting comes from an environment variable, so docker-compose.yml is the single place to configure it.
"""
import os

from flask import Flask

# category key (= image folder in static/) -> (label, image of the category card)
CATEGORIES = {
    "fruits": ("Fruits", "fruitlogo.jpg"),
    "vegetables": ("Vegetables", "vegelogo.jpg"),
    "handmade": ("Homemade", "homemadelogo.jpg"),
    "handcraft": ("Handcraft", "pott.jpg"),
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql://greentastic:greentastic@localhost:5432/greentastic"),
        REDIS_URL=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        ELASTICSEARCH_URL=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"),
        ELASTIC_PASSWORD=os.environ.get("ELASTIC_PASSWORD"),              # user 'elastic'; unset = no auth
        ELASTICSEARCH_CA_CERTS=os.environ.get("ELASTICSEARCH_CA_CERTS"),  # CA of the cluster's TLS certificate
        CACHE_SECONDS=int(os.environ.get("CACHE_SECONDS", "60")),
    )
    if test_config:
        app.config.update(test_config)

    from . import api, auth, cli, manage, shop, simulate, telemetry

    app.register_blueprint(shop.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(manage.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(simulate.bp)
    app.cli.add_command(cli.init_db)
    app.cli.add_command(cli.reindex)

    @app.template_filter("euro")
    def euro(value):
        # prices are Decimal from PostgreSQL, but strings when they come from the Redis cache
        return f"€{float(value):,.2f}"

    @app.context_processor
    def categories():
        return {"categories": CATEGORIES}

    telemetry.setup(app)  # OpenTelemetry: only active when OTEL_EXPORTER_OTLP_ENDPOINT is set
    return app
