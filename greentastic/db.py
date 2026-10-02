"""PostgreSQL access. Each call opens a short-lived connection; rows come back as dicts."""
import psycopg
from flask import current_app
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(current_app.config["DATABASE_URL"], row_factory=dict_row)


def query(sql, params=()):
    """Run a SELECT and return all rows, e.g. [{'id': 1, 'name': 'Apple', ...}]."""
    with connect() as con:
        return con.execute(sql, params).fetchall()


def query_one(sql, params=()):
    """Run a statement and return the first row (or None)."""
    with connect() as con:
        return con.execute(sql, params).fetchone()


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE; leaving the `with` block commits it."""
    with connect() as con:
        con.execute(sql, params)
