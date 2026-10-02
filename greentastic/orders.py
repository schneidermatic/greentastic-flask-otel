"""Cart and orders. An order is created from the cart at checkout (fake - nothing is charged)."""
import logging

from flask import abort

from . import db, products
from .telemetry import cart_additions, order_value, orders_placed, tracer

log = logging.getLogger(__name__)

# order list with the number of products and the total per order
SUMMARY = (
    "SELECT o.*, count(i.id) AS item_count, coalesce(sum(i.price * i.quantity), 0) AS total "
    "FROM orders o LEFT JOIN order_items i ON i.order_id = o.id "
)


def cart(username):
    return db.query(
        "SELECT c.id, p.id AS product_id, p.name, p.price, c.quantity, p.price * c.quantity AS amount "
        "FROM cart_items c JOIN products p ON p.id = c.product_id WHERE c.username = %s ORDER BY c.id",
        (username,),
    )


def add_to_cart(username, product_id, quantity):
    """Put a product into the cart; returns the product, or None if it does not exist."""
    product = products.get(product_id)
    if product is None:
        return None
    quantity = max(int(quantity), 1)
    db.execute("INSERT INTO cart_items (username, product_id, quantity) VALUES (%s, %s, %s)",
               (username, product["id"], quantity))
    cart_additions.add(1, {"category": product["category"]})
    log.info("%s added %d x %s to the cart", username, quantity, product["name"])
    return product


def checkout(username, name, street, city, payment):
    """Turn the cart into an order; returns the new order id, or None if the cart is empty."""
    items = cart(username)
    if not items:
        return None
    total = sum(item["amount"] for item in items)
    # own span around the order transaction, with the business data as attributes
    attributes = {"order.items": len(items), "order.value": float(total), "order.payment": payment}
    with tracer.start_as_current_span("place order", attributes=attributes) as span:
        with db.connect() as con:  # one transaction: create the order, copy the cart into it, empty the cart
            order = con.execute(
                "INSERT INTO orders (username, name, street, city, payment) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (username, name, street, city, payment),
            ).fetchone()
            con.execute(
                "INSERT INTO order_items (order_id, product_name, price, quantity) "
                "SELECT %s, p.name, p.price, c.quantity FROM cart_items c JOIN products p ON p.id = c.product_id "
                "WHERE c.username = %s ORDER BY c.id",
                (order["id"], username),
            )
            con.execute("DELETE FROM cart_items WHERE username = %s", (username,))
        span.set_attribute("order.id", order["id"])
    orders_placed.add(1, {"payment": payment})
    order_value.record(float(total), {"payment": payment})
    log.info("order %d placed by %s: %d products, %.2f EUR", order["id"], username, len(items), total)
    return order["id"]


def of_user(username):
    return db.query(SUMMARY + "WHERE o.username = %s GROUP BY o.id ORDER BY o.id DESC", (username,))


def all_orders():
    return db.query(SUMMARY + "GROUP BY o.id ORDER BY o.id DESC")


def get(order_id, username):
    """The order - only if it belongs to this user, otherwise None."""
    return db.query_one("SELECT * FROM orders WHERE id = %s AND username = %s", (order_id, username))


def items(order_id):
    return db.query("SELECT *, price * quantity AS amount FROM order_items WHERE order_id = %s ORDER BY id",
                    (order_id,))


def _must_be_new(order):
    if order["status"] != "new":
        abort(409, f"order {order['id']} is '{order['status']}' and can no longer be changed")


def update(order, name, street, city, payment, quantities):
    """Change address, payment and quantities ({item id: quantity}, 0 removes the product) of a 'new' order."""
    _must_be_new(order)
    with db.connect() as con:
        con.execute("UPDATE orders SET name = %s, street = %s, city = %s, payment = %s WHERE id = %s",
                    (name, street, city, payment, order["id"]))
        for item_id, quantity in quantities.items():
            if int(quantity) > 0:
                con.execute("UPDATE order_items SET quantity = %s WHERE id = %s AND order_id = %s",
                            (int(quantity), item_id, order["id"]))
            else:
                con.execute("DELETE FROM order_items WHERE id = %s AND order_id = %s", (item_id, order["id"]))
    log.info("order %d changed by %s", order["id"], order["username"])


def delete(order):
    _must_be_new(order)
    db.execute("DELETE FROM orders WHERE id = %s", (order["id"],))  # its items go with it (ON DELETE CASCADE)
    log.info("order %d deleted by %s", order["id"], order["username"])
