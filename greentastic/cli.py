"""Command line tasks, run at container start (see Dockerfile):

    flask --app greentastic init-db   create tables, demo products and the three demo users
    flask --app greentastic reindex   load all products into Elasticsearch
"""
import os
import time
from pathlib import Path

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from . import db, products, search

SQL_DIR = Path(__file__).parent / "sql"

# demo accounts: (env var prefix, default name, role)
DEMO_USERS = [("CUSTOMER", "user", "customer"), ("SELLER", "seller", "seller"), ("ADMIN", "admin", "admin")]


def wait_for(name, check, seconds):
    """Call check() until it stops raising, at most `seconds` long (the other containers start in parallel)."""
    for _ in range(seconds):
        try:
            return check()
        except Exception:
            time.sleep(1)
    raise click.ClickException(f"{name} is not reachable")


@click.command("init-db")
@with_appcontext
def init_db():
    """Create tables and demo data. Safe to run on every start: existing data is kept."""
    wait_for("PostgreSQL", lambda: db.query("SELECT 1"), 60)
    with db.connect() as con:
        con.execute((SQL_DIR / "schema.sql").read_text())
        con.execute((SQL_DIR / "demo_products.sql").read_text())
        for prefix, default_name, role in DEMO_USERS:
            name = os.environ.get(f"{prefix}_USER", default_name)
            password = os.environ.get(f"{prefix}_PASSWORD", default_name)
            con.execute(
                "INSERT INTO users (username, password_hash, email, role) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (username) DO NOTHING",
                (name, generate_password_hash(password), f"{name}@greentastic.local", role),
            )
    click.echo("database ready")


@click.command("reindex")
@with_appcontext
def reindex():
    """Rebuild the Elasticsearch index from PostgreSQL (Elasticsearch needs about a minute to start)."""
    all_products = products.all_products()
    wait_for("Elasticsearch", lambda: search.reindex(all_products), 180)
    click.echo(f"search index ready: {len(all_products)} products")
