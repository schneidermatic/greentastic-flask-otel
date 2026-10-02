"""Redis cache for product lists. If Redis is unreachable the shop keeps working, just without cache."""
import json
import logging

import redis
from flask import current_app

from .telemetry import cache_lookups, tracer

log = logging.getLogger(__name__)


def _redis():
    """One Redis client per app, created on first use."""
    if "redis" not in current_app.extensions:
        current_app.extensions["redis"] = redis.Redis.from_url(
            current_app.config["REDIS_URL"], socket_timeout=1, socket_connect_timeout=1
        )
    return current_app.extensions["redis"]


def get_or_load(key, load):
    """Return the cached value of `key`; on a cache miss call load() and cache its result."""
    # own span: groups the Redis GET with the PostgreSQL query and SETEX of a cache miss
    with tracer.start_as_current_span("cache get_or_load", attributes={"cache.key": key}) as span:
        try:
            cached = _redis().get(key)
        except redis.RedisError as exc:
            log.warning("cache unavailable, reading from the database: %s", exc)
            span.set_attribute("cache.result", "error")
            cache_lookups.add(1, {"result": "error"})
            return load()

        result = "hit" if cached is not None else "miss"
        span.set_attribute("cache.result", result)
        cache_lookups.add(1, {"result": result})
        if cached is not None:
            return json.loads(cached)

        value = load()
        try:
            # default=str stores Decimal prices as strings
            _redis().setex(key, current_app.config["CACHE_SECONDS"], json.dumps(value, default=str))
        except redis.RedisError as exc:
            log.warning("cache unavailable: %s", exc)
        return value


def delete(key):
    try:
        _redis().delete(key)
    except redis.RedisError as exc:
        log.warning("cache unavailable: %s", exc)
