"""SQLite data layer for Spendly.

Provides:
    get_db()   — a SQLite connection with dict-like rows and foreign keys enabled
    init_db()  — creates all tables (safe to call repeatedly)
    seed_db()  — inserts demo data once (no duplicates on repeat runs)
"""

import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

# project root = parent of this file's directory (database/ -> root)
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

# Fixed category list (spec §10)
CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    """Open a connection to the SQLite database.

    Rows are returned as ``sqlite3.Row`` (dict-like access) and foreign key
    enforcement is enabled on every connection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create both tables if they do not already exist. Idempotent."""
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert demo data once. Returns early if any users already exist."""
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing > 0:
            return

        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cur.lastrowid

        # 8 expenses across all 7 categories (Food appears twice), dates in the
        # current month so seed data always looks recent.
        month = date.today().strftime("%Y-%m")  # e.g. "2026-06"
        expenses = [
            (user_id, 450.00, "Food", f"{month}-03", "Groceries"),
            (user_id, 120.50, "Transport", f"{month}-05", "Metro card recharge"),
            (user_id, 1800.00, "Bills", f"{month}-07", "Electricity bill"),
            (user_id, 650.00, "Health", f"{month}-10", "Pharmacy"),
            (user_id, 300.00, "Entertainment", f"{month}-12", "Movie night"),
            (user_id, 2200.00, "Shopping", f"{month}-15", "New shoes"),
            (user_id, 90.00, "Other", f"{month}-18", "Misc"),
            (user_id, 280.00, "Food", f"{month}-20", "Dinner out"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    finally:
        conn.close()
