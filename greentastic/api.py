"""REST API (JSON) for everything the web pages can do - used by scripts and the Locust load test.

Authentication works like in the browser: POST /api/login sets the session cookie, send it with every request.
Errors are JSON as well: {"error": "..."} with status 400, 401, 403, 404 or 409.
"""
from flask import Blueprint, abort, jsonify, request, session
from werkzeug.exceptions import HTTPException

from . import CATEGORIES, accounts, orders, products, search
from .auth import log_in, login_required

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.errorhandler(HTTPException)
def json_error(exc):
    return jsonify(error=exc.description), exc.code


def body(*fields):
    """The JSON request body; 400 if one of the required fields is missing."""
    data = request.get_json(silent=True) or {}
    missing = [field for field in fields if field not in data]
    if missing:
        abort(400, f"missing fields: {', '.join(missing)}")
    return data


# --- catalogue and search (no login needed) ----------------------------------------------------------------

@bp.get("/categories")
def category_list():
    return jsonify([{"key": key, "label": label} for key, (label, _) in CATEGORIES.items()])


@bp.get("/products")
def product_list():
    """All products, or with ?category=fruits only one category (served from the Redis cache)."""
    category = request.args.get("category")
    if category is None:
        return jsonify(products.all_products())
    if category not in CATEGORIES:
        abort(404, f"unknown category {category!r}")
    return jsonify(products.in_category(category))


@bp.get("/products/<int:product_id>")
def product_detail(product_id):
    return jsonify(products.get(product_id) or abort(404, "product not found"))


@bp.get("/search")
def product_search():
    try:
        return jsonify(search.find(request.args.get("q", "")))
    except search.SearchUnavailable:
        abort(503, "search is unavailable")


@bp.get("/suggest")
def suggest():
    """Type-ahead for the search box in the navbar (static/js/search.js); [] if search is unavailable."""
    text = request.args.get("q", "").strip()
    try:
        hits = search.suggest(text) if text else []
    except search.SearchUnavailable:
        hits = []
    return jsonify([{"name": h["name"], "category": h["category"]} for h in hits])


# --- account ---------------------------------------------------------------------------------------------

@bp.post("/register")
def register():
    data = body("username", "password", "email")
    if not accounts.register(data["username"], data["password"], data["email"]):
        abort(409, "user name already taken")
    return jsonify(username=data["username"]), 201


@bp.post("/login")
def login():
    data = body("username", "password")
    user = accounts.authenticate(data["username"], data["password"])
    if user is None:
        abort(401, "wrong user name or password")
    log_in(user)
    return jsonify(username=user["username"], role=user["role"])


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(status="logged out")


@bp.get("/profile")
@login_required()
def profile():
    user = accounts.get(session["username"])
    return jsonify(username=user["username"], email=user["email"], role=user["role"])


@bp.put("/profile")
@login_required()
def profile_update():
    accounts.update_email(session["username"], body("email")["email"])
    return profile()


@bp.put("/profile/password")
@login_required()
def password_change():
    data = body("current_password", "new_password")
    if not accounts.change_password(session["username"], data["current_password"], data["new_password"]):
        abort(403, "current password is not correct")
    return jsonify(status="password changed")


# --- cart and orders -------------------------------------------------------------------------------------

@bp.get("/cart")
@login_required()
def cart():
    return jsonify(orders.cart(session["username"]))


@bp.post("/cart")
@login_required()
def cart_add():
    data = body("product_id")
    if orders.add_to_cart(session["username"], data["product_id"], data.get("quantity", 1)) is None:
        abort(404, "product not found")
    return jsonify(orders.cart(session["username"])), 201


@bp.post("/checkout")
@login_required()
def checkout():
    data = body("name", "street", "city", "payment")
    order_id = orders.checkout(session["username"], data["name"], data["street"], data["city"], data["payment"])
    if order_id is None:
        abort(409, "the cart is empty")
    return order_detail(order_id), 201


@bp.get("/orders")
@login_required()
def order_list():
    return jsonify(orders.of_user(session["username"]))


def own_order(order_id):
    return orders.get(order_id, session["username"]) or abort(404, "order not found")


@bp.get("/orders/<int:order_id>")
@login_required()
def order_detail(order_id):
    return jsonify(order=own_order(order_id), items=orders.items(order_id))


@bp.put("/orders/<int:order_id>")
@login_required()
def order_update(order_id):
    """Body: name, street, city, payment and optionally "quantities": {"<item id>": <quantity>} (0 removes)."""
    data = body("name", "street", "city", "payment")
    orders.update(own_order(order_id), data["name"], data["street"], data["city"], data["payment"],
                  {int(item_id): quantity for item_id, quantity in data.get("quantities", {}).items()})
    return order_detail(order_id)


@bp.delete("/orders/<int:order_id>")
@login_required()
def order_delete(order_id):
    orders.delete(own_order(order_id))
    return jsonify(status="deleted", id=order_id)


# --- back office -----------------------------------------------------------------------------------------

@bp.post("/products")
@login_required("seller", "admin")
def product_add():
    data = body("category", "name", "price", "stock", "unit", "image")
    if data["category"] not in CATEGORIES:
        abort(400, f"unknown category {data['category']!r}")
    product = products.add(data["category"], data["name"], data.get("description", ""), data["price"],
                           data["stock"], data["unit"], data["image"])
    return jsonify(product), 201


@bp.delete("/products/<int:product_id>")
@login_required("seller", "admin")
def product_delete(product_id):
    products.delete(product_id)
    return jsonify(status="deleted", id=product_id)


@bp.get("/manage/orders")
@login_required("seller", "admin")
def all_orders():
    return jsonify(orders.all_orders())


@bp.get("/users")
@login_required("admin")
def user_list():
    return jsonify(accounts.all_users())


@bp.delete("/users/<int:user_id>")
@login_required("admin")
def user_delete(user_id):
    accounts.delete(user_id, session["username"])
    return jsonify(status="deleted", id=user_id)
