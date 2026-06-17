"""Pure data-access helpers for the profile page (Step 5).

Each helper opens its own connection via ``get_db()`` (which enables the
foreign-keys PRAGMA), uses parameterised SQL only, and closes the connection
before returning. No Flask imports here — these are plain functions so they can
be unit-tested in isolation.
"""

import sqlite3
from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return the user's display info, or ``None`` if no such user.

    Returns a dict with ``name``, ``email`` and ``member_since`` (the
    ``created_at`` timestamp formatted as "Month YYYY", e.g. "June 2026").
    """
    db = get_db()
    try:
        row = db.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        db.close()

    if row is None:
        return None

    # created_at is stored by SQLite's datetime('now') as "YYYY-MM-DD HH:MM:SS".
    member_since = datetime.strptime(
        row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")

    return {"name": row["name"], "email": row["email"], "member_since": member_since}


# === Summary stats (Subagent 2) ====================================== #

def get_summary_stats(user_id):
    """Return spending summary for a user.

    dict with ``total_spent`` (float), ``transaction_count`` (int) and
    ``top_category`` (str). With no expenses, returns zeros and "—".
    """
    raise NotImplementedError("Subagent 2 implements this.")


# === Transaction history (Subagent 1) =============================== #

def get_recent_transactions(user_id, limit=10):
    """Return the user's most recent expenses, newest first.

    list of dicts, each with ``date``, ``description``, ``category``,
    ``amount``. Empty list if the user has no expenses.
    """
    raise NotImplementedError("Subagent 1 implements this.")


# === Category breakdown (Subagent 3) ================================ #

def get_category_breakdown(user_id):
    """Return per-category totals ordered by amount descending.

    list of dicts, each with ``name``, ``amount`` (float) and ``pct`` (int
    percentage of total). The ``pct`` values sum to exactly 100. Empty list if
    the user has no expenses.
    """
    raise NotImplementedError("Subagent 3 implements this.")
