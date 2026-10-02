"""Product search with Elasticsearch: one index, one document per product."""
import logging

from elasticsearch import Elasticsearch, helpers
from flask import current_app

from .telemetry import searches

log = logging.getLogger(__name__)
INDEX = "greentastic-products"


class SearchUnavailable(Exception):
    pass


def _es():
    """One Elasticsearch client per app, created on first use."""
    if "elasticsearch" not in current_app.extensions:
        config = current_app.config
        password = config["ELASTIC_PASSWORD"]
        current_app.extensions["elasticsearch"] = Elasticsearch(
            config["ELASTICSEARCH_URL"], request_timeout=3,
            basic_auth=("elastic", password) if password else None,  # the cluster has security enabled
            ca_certs=config["ELASTICSEARCH_CA_CERTS"],               # and TLS with its own CA
        )
    return current_app.extensions["elasticsearch"]


def _document(product):
    return {**product, "price": float(product["price"])}


def reindex(products):
    """Recreate the index and load all products into it."""
    es = _es()
    es.options(ignore_status=404).indices.delete(index=INDEX)
    es.indices.create(index=INDEX, mappings={"properties": {
        "category": {"type": "keyword"},
        "name": {"type": "text"},
        "description": {"type": "text"},
    }})
    helpers.bulk(es, ({"_index": INDEX, "_id": p["id"], "_source": _document(p)} for p in products), refresh=True)


def add(product):
    try:
        _es().index(index=INDEX, id=product["id"], document=_document(product), refresh=True)
    except Exception as exc:  # search is optional: the shop keeps working without it
        log.warning("search unavailable: %s", exc)


def remove(product_id):
    try:
        _es().options(ignore_status=404).delete(index=INDEX, id=product_id, refresh=True)
    except Exception as exc:
        log.warning("search unavailable: %s", exc)


def find(text, size=48):
    """Full-text search over name and description, tolerant to typos ("appel" finds "Apple")."""
    query = {"multi_match": {"query": text, "fields": ["name^3", "description"], "fuzziness": "AUTO"}}
    results = _search("full-text", size, query)
    log.info("search %r: %d results", text, len(results))
    return results


def suggest(text):
    """Product names for the type-ahead dropdown: names starting with (or close to) the typed text."""
    return _search("suggest", 6, {"bool": {"should": [
        {"match_phrase_prefix": {"name": text}},
        {"match": {"name": {"query": text, "fuzziness": "AUTO"}}},
    ]}})


def _search(kind, size, query):
    try:
        response = _es().search(index=INDEX, size=size, query=query)
    except Exception as exc:
        searches.add(1, {"kind": kind, "outcome": "unavailable"})
        log.error("search unavailable: %s", exc)
        raise SearchUnavailable(str(exc)) from exc
    results = [hit["_source"] for hit in response["hits"]["hits"]]
    searches.add(1, {"kind": kind, "outcome": "found" if results else "no results"})
    return results
