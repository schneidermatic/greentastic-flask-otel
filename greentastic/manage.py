"""Back office: sellers and admins manage products and see all orders; only admins manage users."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from . import CATEGORIES, accounts, orders, products
from .auth import login_required

bp = Blueprint("manage", __name__, url_prefix="/manage")


@bp.route("/products")
@login_required("seller", "admin")
def product_list():
    return render_template("manage_products.html", products=products.all_products())


@bp.route("/products/new", methods=["GET", "POST"])
@login_required("seller", "admin")
def product_new():
    if request.method == "POST":
        form = request.form
        products.add(form["category"], form["name"], form["description"], form["price"],
                     form["stock"], form["unit"], form["image"])
        flash(f"{form['name']} added.", "success")
        return redirect(url_for("manage.product_list"))
    return render_template("manage_product_form.html", categories=CATEGORIES)


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required("seller", "admin")
def product_delete(product_id):
    products.delete(product_id)
    flash("Product deleted.", "success")
    return redirect(url_for("manage.product_list"))


@bp.route("/orders")
@login_required("seller", "admin")
def order_list():
    return render_template("manage_orders.html", orders=orders.all_orders())


@bp.route("/users")
@login_required("admin")
def user_list():
    return render_template("manage_users.html", users=accounts.all_users())


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required("admin")
def user_delete(user_id):
    accounts.delete(user_id, session["username"])
    flash("User deleted.", "success")
    return redirect(url_for("manage.user_list"))
