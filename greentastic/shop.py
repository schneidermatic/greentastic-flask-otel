"""Customer pages: browse, search, cart, checkout and orders; the logic lives in products/orders/search.py."""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from . import CATEGORIES, orders, products, search
from .auth import login_required

bp = Blueprint("shop", __name__)


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/contact")
def contact():
    return render_template("contact.html")


@bp.route("/category/<category>")
def category(category):
    if category not in CATEGORIES:
        abort(404)
    return render_template("category.html", category=category, products=products.in_category(category))


@bp.route("/search")
def search_page():
    text = request.args.get("q", "").strip()
    results, unavailable = [], False
    if text:
        try:
            results = search.find(text)
        except search.SearchUnavailable:
            unavailable = True
    return render_template("search.html", q=text, results=results, unavailable=unavailable)


@bp.route("/cart")
@login_required()
def cart():
    return render_template("cart.html", items=orders.cart(session["username"]))


@bp.route("/cart/add", methods=["POST"])
@login_required()
def cart_add():
    product = orders.add_to_cart(session["username"], request.form["product_id"], request.form.get("quantity", 1))
    if product is None:
        abort(404)
    flash(f"{product['name']} added to your cart.", "success")
    return redirect(url_for("shop.cart"))


@bp.route("/checkout", methods=["GET", "POST"])
@login_required()
def checkout():
    username = session["username"]
    if request.method == "POST":
        form = request.form
        order_id = orders.checkout(username, form["name"], form["street"], form["city"], form["payment"])
        if order_id:
            flash("Thank you! Your order has been placed (demo - no payment was taken).", "success")
            return redirect(url_for("shop.order_detail", order_id=order_id))
    items = orders.cart(username)
    if not items:
        return redirect(url_for("shop.cart"))
    return render_template("checkout.html", items=items)


@bp.route("/orders")
@login_required()
def order_list():
    return render_template("orders.html", orders=orders.of_user(session["username"]))


def own_order(order_id):
    """The logged-in user's order with this id (404 for other users' orders)."""
    order = orders.get(order_id, session["username"])
    if order is None:
        abort(404)
    return order


@bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
@login_required()
def order_detail(order_id):
    """Show one order; while it is 'new' the customer can change address, payment and quantities."""
    order = own_order(order_id)
    if request.method == "POST":
        form = request.form
        quantities = {int(key.removeprefix("quantity_")): value
                      for key, value in form.items() if key.startswith("quantity_")}
        orders.update(order, form["name"], form["street"], form["city"], form["payment"], quantities)
        flash("Order updated.", "success")
        return redirect(url_for("shop.order_detail", order_id=order_id))
    return render_template("order_detail.html", order=order, items=orders.items(order_id))


@bp.route("/orders/<int:order_id>/delete", methods=["POST"])
@login_required()
def order_delete(order_id):
    orders.delete(own_order(order_id))
    flash(f"Order {order_id} deleted.", "success")
    return redirect(url_for("shop.order_list"))
