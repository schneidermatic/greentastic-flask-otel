"""Endpoints that fail or are slow on purpose - to see what errors look like in traces, metrics and logs.

    GET /api/simulate/                 list of the simulations
    GET /api/simulate/error            handled exception in an own span            -> 500
    GET /api/simulate/crash            unhandled exception (Flask turns it into a 500)
    GET /api/simulate/slow?seconds=2   slow SQL query (pg_sleep)                    -> 200, but slow
    GET /api/simulate/db-error         SQL error in PostgreSQL (unknown table)      -> 500
    GET /api/simulate/search-error     invalid query, rejected by Elasticsearch     -> 502
    GET /api/simulate/timeout          external payment provider does not answer   -> 504
    GET /api/simulate/random           one of the above, chosen at random
"""
import logging
import random
import time

import psycopg
from flask import Blueprint, jsonify, request
from opentelemetry.trace import SpanKind, Status, StatusCode
from werkzeug.exceptions import HTTPException

from . import db, search
from .api import json_error
from .telemetry import simulated_errors, tracer

bp = Blueprint("simulate", __name__, url_prefix="/api/simulate")
bp.register_error_handler(HTTPException, json_error)
log = logging.getLogger(__name__)


def fail(span, exc, status):
    """Mark the span as failed, log the error and answer with a JSON error."""
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))
    log.error("simulated %s: %s", type(exc).__name__, exc)
    return jsonify(error=str(exc)), status


@bp.get("/")
def overview():
    lines = [line.split(maxsplit=2) for line in __doc__.splitlines() if line.strip().startswith("GET")]
    return jsonify([{"path": path, "what": " ".join(what.split())} for _, path, what in lines])


@bp.get("/error")
def error():
    simulated_errors.add(1, {"kind": "error"})
    with tracer.start_as_current_span("failing step") as span:
        try:
            raise RuntimeError("simulated failure in a processing step")
        except RuntimeError as exc:
            return fail(span, exc, 500)


@bp.get("/crash")
def crash():
    simulated_errors.add(1, {"kind": "crash"})
    return {"result": 1 / 0}  # ZeroDivisionError - nobody catches it, Flask logs the traceback


@bp.get("/slow")
def slow():
    seconds = min(float(request.args.get("seconds", random.uniform(1, 3))), 10)
    simulated_errors.add(1, {"kind": "slow"})
    log.warning("slow request: the database sleeps %.1f s", seconds)
    db.query("SELECT pg_sleep(%s)", (seconds,))  # shows up as a long SQL span in the trace
    return jsonify(status="ok", seconds=round(seconds, 2))


@bp.get("/db-error")
def db_error():
    simulated_errors.add(1, {"kind": "db-error"})
    with tracer.start_as_current_span("load report") as span:
        try:
            db.query("SELECT * FROM monthly_report")  # this table does not exist
        except psycopg.Error as exc:
            return fail(span, exc, 500)


@bp.get("/search-error")
def search_error():
    simulated_errors.add(1, {"kind": "search-error"})
    with tracer.start_as_current_span("advanced search") as span:
        try:
            # unbalanced parenthesis: Elasticsearch rejects the query with 400 Bad Request
            search._es().search(index=search.INDEX, query={"query_string": {"query": "name:(apple"}})
        except Exception as exc:
            return fail(span, exc, 502)


@bp.get("/timeout")
def timeout():
    """A call to an external payment provider that never answers (simulated: no real network call)."""
    seconds = min(float(request.args.get("seconds", 2)), 10)
    simulated_errors.add(1, {"kind": "timeout"})
    attributes = {"http.request.method": "POST", "server.address": "payment-provider", "peer.service": "payment-provider"}
    with tracer.start_as_current_span("POST payment-provider", kind=SpanKind.CLIENT, attributes=attributes) as span:
        time.sleep(seconds)
        return fail(span, TimeoutError(f"payment provider did not answer within {seconds:g} s"), 504)


@bp.get("/random")
def random_failure():
    return random.choice([error, crash, slow, db_error, search_error, timeout])()
