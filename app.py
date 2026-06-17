import math
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

app = Flask(__name__)
# Signed-cookie sessions. Use SECRET_KEY in production; dev fallback otherwise.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Fixed expense categories (must match the seed data from Step 1).
CATEGORIES = ["Food", "Transport", "Bills", "Health",
              "Entertainment", "Shopping", "Other"]

# Ensure the database schema exists and demo data is seeded on startup.
# Runs under both `python app.py` and `flask run`.
with app.app_context():
    init_db()
    seed_db()


# Expose the logged-in user to every template (navbar, etc.).
@app.context_processor
def inject_current_user():
    if "user_id" in session:
        return {"current_user": {"id": session["user_id"], "name": session.get("user_name")}}
    return {"current_user": None}


def login_required(view):
    """Redirect to the login page if there is no active session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Already-authenticated users shouldn't see the register form.
    if "user_id" in session:
        return redirect(url_for("profile"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Validation
        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            return render_template("register.html", error="Please enter a valid email address.")
        if len(password) < 8:
            return render_template(
                "register.html", error="Password must be at least 8 characters."
            )

        # Create the user (parameterized); UNIQUE email enforced by the DB.
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template(
                "register.html", error="An account with this email already exists."
            )
        finally:
            db.close()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    # Already-authenticated users shouldn't see the login form.
    if "user_id" in session:
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="All fields are required.")

        db = get_db()
        try:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        finally:
            db.close()

        # Generic error — do not reveal which field was wrong.
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
@login_required
def profile():
    # Step 5: every section is driven by live DB queries scoped to the
    # logged-in user. Query helpers live in database/queries.py; this route
    # maps their output onto the variable names profile.html already consumes.
    uid = session["user_id"]

    # --- User info (orchestrator) --- #
    # get_user_by_id returns {name, email, member_since}; the template reads
    # user.created_at for the "Member since" line.
    info = get_user_by_id(uid)
    user = {
        "name": info["name"],
        "email": info["email"],
        "created_at": info["member_since"],
    }

    # --- Summary stats section (Subagent 2) --- #
    # TODO(Subagent 2): call get_summary_stats(uid) and map its keys
    # {total_spent, transaction_count, top_category} onto the template vars
    # {total_amount, total_count, top_category}.
    total_amount = 0
    total_count = 0
    top_category = "—"

    # --- Transaction history section (Subagent 1) --- #
    # TODO(Subagent 1): call get_recent_transactions(uid). Its keys
    # (date/description/category/amount) already match the template — no mapping.
    recent = []

    # --- Category breakdown section (Subagent 3) --- #
    # TODO(Subagent 3): call get_category_breakdown(uid) and map each item
    # {name, amount, pct} onto the template's {category, total, pct}.
    breakdown = []

    return render_template(
        "profile.html",
        user=user,
        total_count=total_count,
        total_amount=total_amount,
        recent=recent,
        breakdown=breakdown,
        top_category=top_category,
    )


@app.route("/analytics")
@login_required
def analytics():
    # Login-protected; logged-out users are redirected to login by login_required.
    return render_template("analytics.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_str = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        # Preserve submitted values when re-rendering on error.
        submitted = {
            "amount": amount,
            "category": category,
            "date": date_str,
            "description": description,
        }

        def reject(message):
            return render_template(
                "add_expense.html",
                error=message,
                categories=CATEGORIES,
                today=date.today().isoformat(),
                expense=submitted,
            )

        # Validate amount: required, numeric, finite, greater than zero.
        # float() also accepts "nan"/"inf"/overflow literals, which slip past
        # a bare "<= 0" check — guard with isfinite.
        try:
            amount_value = float(amount)
        except ValueError:
            return reject("Please enter a valid amount.")
        if not math.isfinite(amount_value) or amount_value <= 0:
            return reject("Amount must be greater than zero.")

        # Validate category against the server-side list (don't trust the form).
        if category not in CATEGORIES:
            return reject("Please choose a valid category.")

        # Validate date format and normalize to zero-padded YYYY-MM-DD so it
        # matches the LIKE 'YYYY-MM-%' month query (strptime accepts "2026-6-8").
        try:
            date_str = datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return reject("Please enter a valid date.")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], amount_value, category, date_str,
                 description or None),
            )
            db.commit()
        finally:
            db.close()

        return redirect(url_for("profile"))

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        today=date.today().isoformat(),
        expense=None,
    )


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
