"""Web pages for login, registration, profile and logout; the logic lives in accounts.py."""
import functools

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from . import accounts

bp = Blueprint("auth", __name__)


def login_required(*roles):
    """Decorator: the view needs a logged-in user, optionally with one of the given roles."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if "username" not in session:
                if request.blueprint == "api":  # the REST API answers with JSON instead of the login page
                    return jsonify(error="login required"), 401
                return redirect(url_for("auth.login"))
            if roles and session["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def log_in(user):
    session["username"], session["role"] = user["username"], user["role"]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = accounts.authenticate(request.form["username"], request.form["password"])
        if user:
            log_in(user)
            flash(f"Welcome, {user['username']}!", "success")
            return redirect(url_for("shop.home"))
        flash("Wrong user name or password.", "danger")
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form = request.form
        if accounts.register(form["username"], form["password"], form["email"]):
            flash("Account created - please log in.", "success")
            return redirect(url_for("auth.login"))
        flash("This user name is already taken.", "danger")
    return render_template("register.html")


@bp.route("/profile", methods=["GET", "POST"])
@login_required()
def profile():
    """Show the own account; the page has two forms: change email, change password."""
    username = session["username"]
    if request.method == "POST":
        form = request.form
        if form["action"] == "email":
            accounts.update_email(username, form["email"])
            flash("Email address saved.", "success")
        elif form["new_password"] != form["confirm_password"]:
            flash("The two new passwords do not match.", "danger")
        elif accounts.change_password(username, form["current_password"], form["new_password"]):
            flash("Password changed.", "success")
        else:
            flash("Your current password is not correct.", "danger")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html", user=accounts.get(username))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("shop.home"))
