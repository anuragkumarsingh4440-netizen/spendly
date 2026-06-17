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
    db = get_db()
    try:
        total_spent = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        transaction_count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        top_row = db.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        db.close()

    if transaction_count == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    return {
        "total_spent": float(total_spent),
        "transaction_count": int(transaction_count),
        "top_category": top_row["category"],
    }


# === Transaction history (Subagent 1) =============================== #

def get_recent_transactions(user_id, limit=10):
    """Return the user's most recent expenses, newest first.

    list of dicts, each with ``date``, ``description``, ``category``,
    ``amount``. Empty list if the user has no expenses.
    """
    db = get_db()
    try:
        rows = db.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        db.close()

    return [dict(row) for row in rows]


# === Category breakdown (Subagent 3) ================================ #

def get_category_breakdown(user_id):
    """Return per-category totals ordered by amount descending.

    list of dicts, each with ``name``, ``amount`` (float) and ``pct`` (int
    percentage of total). The ``pct`` values sum to exactly 100. Empty list if
    the user has no expenses.
    """
    db = get_db()
    try:
        rows = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        db.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)
    breakdown = [
        {
            "name": row["category"],
            "amount": float(row["total"]),
            "pct": round(row["total"] / grand_total * 100),
        }
        for row in rows
    ]

    # Adjust the largest category (first, since ordered desc) so pcts sum to 100.
    breakdown[0]["pct"] += 100 - sum(item["pct"] for item in breakdown)

    return breakdown
