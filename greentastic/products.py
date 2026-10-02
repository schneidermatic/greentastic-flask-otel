"""The product catalogue. Keeps PostgreSQL (source of truth), Redis (cache) and Elasticsearch (search) in sync."""
import logging

from . import cache, db, search

log = logging.getLogger(__name__)


def in_category(category):
    """Products of one category - served from Redis, loaded from PostgreSQL on a cache miss."""
    return cache.get_or_load(
        f"products:{category}",
        lambda: db.query("SELECT * FROM products WHERE category = %s ORDER BY name", (category,)),
    )


def all_products():
    return db.query("SELECT * FROM products ORDER BY category, name")


def get(product_id):
    return db.query_one("SELECT * FROM products WHERE id = %s", (product_id,))


def add(category, name, description, price, stock, unit, image):
    product = db.query_one(
        "INSERT INTO products (category, name, description, price, stock, unit, image) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (category, name, description, price, stock, unit, image),
    )
    cache.delete(f"products:{category}")
    search.add(product)
    log.info("product %d %s added to %s", product["id"], name, category)
    return product


def delete(product_id):
    product = db.query_one("DELETE FROM products WHERE id = %s RETURNING category", (product_id,))
    if product:
        cache.delete(f"products:{product['category']}")
        search.remove(product_id)
        log.info("product %d deleted", product_id)
