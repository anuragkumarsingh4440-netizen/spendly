import math
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
    get_expense_by_id,
)
from database.date_filter import resolve_range, is_valid_date, PRESETS

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

    # --- Date filter (Step 6) --- #
    # Read optional start/end/range from the query string and resolve to a
    # concrete (start, end) pair. resolve_range fails safe to all-time (None,
    # None) for partial, malformed or unknown input, so every section below
    # behaves exactly as in Step 5 when no valid filter is supplied.
    range_key = request.args.get("range")
    raw_start = request.args.get("start")
    raw_end = request.args.get("end")
    start, end = resolve_range(range_key=range_key, start=raw_start, end=raw_end)
    filtered = start is not None and end is not None

    # Which preset (if any) actually drove the result, so the template can mark
    # it active off the *resolved* state rather than the raw range_key. Explicit
    # dates win in resolve_range, so a preset is only "active" when no valid
    # explicit pair was supplied.
    explicit_dates = is_valid_date(raw_start) and is_valid_date(raw_end)
    active_preset = range_key if (range_key in PRESETS and not explicit_dates) else None

    # --- User info (orchestrator) --- #
    # User info is never date-scoped. get_user_by_id returns
    # {name, email, member_since}; the template reads user.created_at.
    info = get_user_by_id(uid)
    user = {
        "name": info["name"],
        "email": info["email"],
        "created_at": info["member_since"],
    }

    # --- Summary stats section (Subagent 2) --- #
    stats = get_summary_stats(uid, start=start, end=end)
    total_amount = stats["total_spent"]
    total_count = stats["transaction_count"]
    top_category = stats["top_category"]

    # --- Transaction history section (Subagent 1) --- #
    # Keys already match the template (date/description/category/amount).
    recent = get_recent_transactions(uid, start=start, end=end)

    # --- Category breakdown section (Subagent 3) --- #
    # Map helper keys {name, amount, pct} onto the template's {category, total, pct}.
    breakdown = [
        {"category": item["name"], "total": item["amount"], "pct": item["pct"]}
        for item in get_category_breakdown(uid, start=start, end=end)
    ]

    return render_template(
        "profile.html",
        user=user,
        total_count=total_count,
        total_amount=total_amount,
        recent=recent,
        breakdown=breakdown,
        top_category=top_category,
        start=start,
        end=end,
        active_preset=active_preset,
        filtered=filtered,
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


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    # Ownership gate: load the expense scoped to the logged-in user. A missing
    # expense — or one belonging to another user — is indistinguishable here and
    # returns 404, so we never leak whether an id exists for someone else.
    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_str = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        # Preserve submitted values (and the id, so the form action still targets
        # this expense) when re-rendering on error.
        submitted = {
            "id": id,
            "amount": amount,
            "category": category,
            "date": date_str,
            "description": description,
        }

        def reject(message):
            return render_template(
                "edit_expense.html",
                error=message,
                categories=CATEGORIES,
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

        # Validate date format and normalize to zero-padded YYYY-MM-DD.
        try:
            date_str = datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return reject("Please enter a valid date.")

        # Update in place, ownership-scoped: the user_id predicate ensures a user
        # can never overwrite someone else's row even by guessing the id.
        db = get_db()
        try:
            db.execute(
                "UPDATE expenses SET amount = ?, category = ?, date = ?, "
                "description = ? WHERE id = ? AND user_id = ?",
                (amount_value, category, date_str, description or None,
                 id, session["user_id"]),
            )
            db.commit()
        finally:
            db.close()

        return redirect(url_for("profile"))

    return render_template(
        "edit_expense.html",
        categories=CATEGORIES,
        expense=expense,
    )


@app.route("/expenses/<int:id>/delete", methods=["POST"])
@login_required
def delete_expense(id):
    # POST-only: a destructive action must never fire from a link or prefetch.
    # A GET to this route returns 405 (only POST is registered).
    #
    # Ownership gate: a missing expense — or one belonging to another user — is
    # indistinguishable here and returns 404, so we never leak whether an id
    # exists for someone else.
    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    # Ownership-scoped delete: the user_id predicate ensures a user can never
    # remove someone else's row even by guessing the id.
    db = get_db()
    try:
        db.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (id, session["user_id"]),
        )
        db.commit()
    finally:
        db.close()

    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
