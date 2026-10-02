"""User accounts: one `users` table, the `role` column is customer, seller or admin."""
import logging

from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .telemetry import logins

log = logging.getLogger(__name__)


def get(username):
    return db.query_one("SELECT * FROM users WHERE username = %s", (username,))


def all_users():
    return db.query("SELECT id, username, email, role FROM users ORDER BY role, username")


def authenticate(username, password):
    """The user if name and password are correct, otherwise None."""
    user = get(username)
    if user and check_password_hash(user["password_hash"], password):
        logins.add(1, {"outcome": "success", "role": user["role"]})
        log.info("user %s logged in", username)
        return user
    logins.add(1, {"outcome": "failure"})
    log.warning("failed login for user name %r", username)
    return None


def register(username, password, email):
    """Create a customer account; False if the user name is already taken."""
    if get(username):
        return False
    db.execute(
        "INSERT INTO users (username, password_hash, email, role) VALUES (%s, %s, %s, 'customer')",
        (username, generate_password_hash(password), email),
    )
    log.info("new customer account %s", username)
    return True


def update_email(username, email):
    db.execute("UPDATE users SET email = %s WHERE username = %s", (email, username))


def change_password(username, current_password, new_password):
    """False if the current password is wrong."""
    if not check_password_hash(get(username)["password_hash"], current_password):
        return False
    db.execute("UPDATE users SET password_hash = %s WHERE username = %s",
               (generate_password_hash(new_password), username))
    log.info("user %s changed the password", username)
    return True


def delete(user_id, current_username):
    """Delete a user - but never the one who is logged in."""
    db.execute("DELETE FROM users WHERE id = %s AND username <> %s", (user_id, current_username))
